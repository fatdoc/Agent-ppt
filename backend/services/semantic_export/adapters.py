"""Explicit bridge from EditableImage, plus future editor boundary.

Annotations are necessary when extraction has no semantic ownership. Unknown or
unaccounted elements fail rather than disappearing. Screenshot descendants are
retained as source IDs in the report, not duplicated as native text.
"""
from typing import Protocol
from copy import deepcopy
from .model import Page, Node, load_page


class EditorAdapter(Protocol):
    def to_editor(self, page: Page) -> dict: ...
    def from_editor(self, data: dict, *, base: Page) -> Page: ...
    # Adapters must report unsupported features; lossy round trips cannot be ready.


def from_editable_image(image, *, page_metadata, annotations, assets):
    """annotations keyed by existing element_id; no OCR or Provider invoked.

Each annotation supplies module/column/style/asset mapping and optional reviewed
box. Groups/native card bases can be included in page_metadata.nodes. Geometry
otherwise uses bbox_global, never the recursive local coordinates.
"""
    data = deepcopy(page_metadata)
    data['assets'] = assets
    nodes = data.setdefault('nodes', [])
    retained = []
    seen = set()

    def visit(element):
        seen.add(element.element_id)
        if element.element_id not in annotations:
            raise ValueError(f'unassigned extraction element: {element.element_id}')
        spec = deepcopy(annotations[element.element_id])
        spec['id'] = element.element_id
        b = element.bbox_global
        spec.setdefault('box', dict(x=b.x0, y=b.y0, w=b.width, h=b.height))
        if spec['kind'] == 'text':
            if element.element_type != 'text':
                raise ValueError('non-text extraction needs explicit conversion')
            extracted = element.content or ''
            actual = '\n'.join(''.join(r['text'] for r in p['runs']) for p in spec['text']['paragraphs'])
            if actual != extracted:
                raise ValueError('annotation rewrites extracted text; use tracked correction')
        nodes.append(spec)
        if spec.get('picture', {}).get('role') == 'screenshot':
            def remember(child):
                retained.append(child.element_id)
                seen.add(child.element_id)
                for c in child.children:
                    remember(c)
            for c in element.children:
                remember(c)
        else:
            for child in element.children:
                visit(child)
    for element in image.elements:
        visit(element)
    if set(annotations)-seen:
        raise ValueError('annotations reference unknown extraction IDs')
    data.setdefault('warnings', []).extend(f'{i}: retained inside whole screenshot' for i in retained)
    return load_page(data)


def merge_paragraphs(nodes: list[Node]):
    """Caller-selected lines only. No content filtering or geometric guessing."""
    if not nodes or any(n.kind != 'text' for n in nodes):
        raise ValueError('text nodes required')
    first = nodes[0]
    if any((n.module_id, n.column_id, n.parent_id, n.rotation) != (first.module_id, first.column_id, first.parent_id, 0) for n in nodes):
        raise ValueError('cannot merge across columns/cards or rotated text')
    ordered = sorted(nodes, key=lambda n: n.box.y)
    for a, b in zip(ordered, ordered[1:]):
        if abs(a.box.x-b.box.x) > 2 or b.box.y < a.box.y or b.box.y-(a.box.y+a.box.h) > max(a.box.h, b.box.h):
            raise ValueError('lines are not a continuous aligned paragraph')
        if [r.model_dump(exclude={'text'}) for r in a.text.paragraphs[0].runs] != [r.model_dump(exclude={'text'}) for r in b.text.paragraphs[0].runs]:
            raise ValueError('incompatible paragraph styles')
    # One native textbox, original paragraph order/text retained exactly.
    data = first.model_dump(mode='json')
    x, y = min(n.box.x for n in nodes), min(n.box.y for n in nodes)
    data['box'] = dict(x=x, y=y, w=max(n.box.x+n.box.w for n in nodes)-x, h=max(n.box.y+n.box.h for n in nodes)-y)
    data['text']['paragraphs'] = [p.model_dump(mode='json') for n in ordered for p in n.text.paragraphs]
    data['provenance']['warnings'].append('merged source IDs: '+','.join(n.id for n in ordered))
    data['provenance']['confidence'] = min(n.provenance.confidence for n in nodes)
    return Node.model_validate(data)
