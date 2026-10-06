"""Versioned editor-neutral page contract. All geometry is page-absolute CSS px.

No inferred deletion, background inpainting fallback, or editor-private JSON.
Schema v1 deliberately supports simple rectangular tables and identity groups.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Annotated, Literal
from pathlib import PurePosixPath
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

ID = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')]
Digest = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]
Color = Annotated[str, Field(pattern=r'^[A-Fa-f0-9]{6}$')]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, validate_assignment=True)


class Box(Contract):
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    w: float = Field(gt=0)
    h: float = Field(gt=0)

    def overlap(self, other):
        return max(0, min(self.x+self.w, other.x+other.w)-max(self.x, other.x)) * max(0, min(self.y+self.h, other.y+other.h)-max(self.y, other.y))


class Provenance(Contract):
    method: Literal['manual_fixture', 'structured', 'ocr', 'manual_correction']
    source_ref: ID
    source_box: Box | None = None
    confidence: float = Field(default=1, ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
    # Draft copy is retained separately; it must never silently override visible text.
    proposed_text: str | None = None
    text_alignment: Literal['verified', 'mismatch', 'unverified'] = 'verified'


class Asset(Contract):
    id: ID
    uri: str
    sha256: Digest
    media_type: Literal['image/png', 'image/jpeg', 'image/svg+xml']
    user_id: ID
    project_id: ID
    provenance: Provenance

    @field_validator('uri')
    @classmethod
    def relative_asset(cls, value):
        p = PurePosixPath(value)
        if not value or p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value or '%' in value or str(p) != value:
            raise ValueError('asset URI must be a canonical project-relative path')
        return value


class Run(Contract):
    text: str
    size: float = Field(default=24, gt=0, le=400)  # CSS px, converted to pt at 96 dpi
    font: str = 'Noto Sans CJK SC'
    color: Color = '203040'
    bold: bool = False
    italic: bool = False


class Paragraph(Contract):
    runs: list[Run] = Field(min_length=1)
    align: Literal['left', 'center', 'right'] = 'left'
    line_spacing: float = Field(default=1.15, gt=0, le=5)
    space_after: float = Field(default=0, ge=0)


class Crop(Contract):
    left: float = Field(default=0, ge=0, lt=1)
    top: float = Field(default=0, ge=0, lt=1)
    right: float = Field(default=0, ge=0, lt=1)
    bottom: float = Field(default=0, ge=0, lt=1)

    @model_validator(mode='after')
    def valid_crop(self):
        if self.left+self.right >= 1 or self.top+self.bottom >= 1:
            raise ValueError('crop removes entire image')
        return self


class Text(Contract):
    paragraphs: list[Paragraph] = Field(min_length=1)


class Shape(Contract):
    geometry: Literal['rect', 'roundRect', 'ellipse', 'rightArrow'] = 'rect'
    fill: Color = 'FFFFFF'
    stroke: Color | None = None
    stroke_width: float = Field(default=1, ge=0)


class Picture(Contract):
    asset_id: ID
    fallback_asset_id: ID | None = None
    role: Literal['photo', 'screenshot', 'icon']
    crop: Crop = Field(default_factory=Crop)
    preserve_whole: bool = False

    @model_validator(mode='after')
    def whole_screenshot(self):
        if self.role == 'screenshot' and (not self.preserve_whole or any(self.crop.model_dump().values())):
            raise ValueError('screenshots must remain whole images')
        return self


class Table(Contract):
    rows: list[list[str]] = Field(min_length=1)
    column_weights: list[float] = Field(min_length=1)
    font: str = 'Noto Sans CJK SC'
    size: float = Field(default=22, gt=0, le=100)
    header_fill: Color = '203040'
    body_fill: Color = 'F2F5F8'
    text_color: Color = '203040'
    header_color: Color = 'FFFFFF'

    @model_validator(mode='after')
    def rectangular(self):
        if any(not math.isfinite(v) or v <= 0 for v in self.column_weights) or any(len(row) != len(self.column_weights) for row in self.rows):
            raise ValueError('table must be rectangular with positive column weights')
        return self


class Node(Contract):
    id: ID
    name: str = Field(min_length=1)
    kind: Literal['text', 'shape', 'image', 'svg', 'table']
    box: Box
    rotation: float = Field(default=0, ge=-360, le=360)
    layer: int = Field(ge=0)
    module_id: ID
    column_id: ID = 'main'
    parent_id: ID | None = None
    provenance: Provenance
    text: Text | None = None
    shape: Shape | None = None
    picture: Picture | None = None
    table: Table | None = None

    @model_validator(mode='after')
    def payload(self):
        required = {'text': 'text', 'shape': 'shape', 'image': 'picture', 'svg': 'picture', 'table': 'table'}[self.kind]
        if any((getattr(self, key) is not None) != (key == required) for key in ('text', 'shape', 'picture', 'table')):
            raise ValueError('node kind and payload disagree')
        if self.kind == 'table' and self.rotation:
            raise ValueError('rotated native tables unsupported in schema v1')
        return self


class Group(Contract):
    id: ID
    name: str = Field(min_length=1)
    module_id: ID
    parent_id: ID | None = None


class Correction(Contract):
    revision: ID
    object_id: ID
    reason: str
    before_sha256: Digest
    after_sha256: Digest


class Source(Contract):
    id: ID
    revision: ID
    sha256: Digest


class Page(Contract):
    schema_version: Literal['1.0'] = '1.0'
    id: ID
    revision: ID
    source: Source
    user_id: ID
    project_id: ID
    width: float = Field(gt=0, le=5376)
    height: float = Field(gt=0, le=5376)
    unit: Literal['px'] = 'px'
    dpi: Literal[96] = 96
    background: Color = 'FFFFFF'  # Only native solid backgrounds in phase 1.
    assets: list[Asset] = Field(default_factory=list)
    nodes: list[Node] = Field(min_length=1)
    groups: list[Group] = Field(default_factory=list)
    corrections: list[Correction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: Literal['ready', 'needs_correction'] = 'ready'

    @model_validator(mode='after')
    def semantic_integrity(self):
        ids = [o.id for o in self.nodes+self.groups]
        if len(ids) != len(set(ids)):
            raise ValueError('duplicate object ID')
        if len({n.layer for n in self.nodes}) != len(self.nodes):
            raise ValueError('ambiguous layer order')
        assets = {a.id: a for a in self.assets}
        if len(assets) != len(self.assets):
            raise ValueError('duplicate asset ID')
        for a in self.assets:
            if (a.user_id, a.project_id) != (self.user_id, self.project_id):
                raise ValueError('cross-project asset')
            if a.sha256 == self.source.sha256:
                raise ValueError('full source page asset forbidden')
        groups = {g.id: g for g in self.groups}
        for obj in self.nodes+self.groups:
            seen = {obj.id}
            parent = obj.parent_id
            while parent:
                if parent not in groups or parent in seen:
                    raise ValueError('missing or cyclic group parent')
                seen.add(parent)
                if groups[parent].module_id != obj.module_id:
                    raise ValueError('group crosses semantic module')
                parent = groups[parent].parent_id
        ordered = sorted(self.nodes, key=lambda n: n.layer)
        for group in self.groups:
            positions = [i for i, n in enumerate(ordered) if group.id in self.ancestors(n)]
            if not positions or positions != list(range(min(positions), max(positions)+1)):
                raise ValueError('group must contain contiguous layers; regrouping would change occlusion')
        for n in self.nodes:
            b = n.box
            angle = math.radians(n.rotation)
            rw, rh = abs(b.w*math.cos(angle))+abs(b.h*math.sin(angle)), abs(b.w*math.sin(angle))+abs(b.h*math.cos(angle))
            if b.x+b.w/2-rw/2 < -0.01 or b.y+b.h/2-rh/2 < -0.01 or b.x+b.w/2+rw/2 > self.width+0.01 or b.y+b.h/2+rh/2 > self.height+0.01:
                raise ValueError('object outside page')
            if n.picture:
                p = n.picture
                for ref in (p.asset_id, p.fallback_asset_id):
                    if ref and ref not in assets:
                        raise ValueError('missing asset relationship')
                a = assets[p.asset_id]
                if n.kind == 'svg':
                    if a.media_type != 'image/svg+xml' or not p.fallback_asset_id or assets[p.fallback_asset_id].media_type != 'image/png':
                        raise ValueError('SVG needs source SVG and PNG compatibility fallback')
                elif a.media_type == 'image/svg+xml':
                    raise ValueError('SVG must use svg node')
                if b.w*b.h >= self.width*self.height*0.90:
                    raise ValueError('full-page content image forbidden')
        screenshots = [n for n in self.nodes if n.picture and n.picture.role == 'screenshot']
        for n in self.nodes:
            if n.kind == 'text' and any(n.box.overlap(s.box) / (n.box.w*n.box.h) > 0.5 for s in screenshots):
                raise ValueError('native text overlaps preserved screenshot')
        return self

    def ancestors(self, node):
        groups = {g.id: g for g in self.groups}
        result, parent = [], node.parent_id
        while parent:
            result.append(parent)
            parent = groups[parent].parent_id
        return result

    def issues(self):
        result = list(self.warnings)
        for n in self.nodes:
            result += [f'{n.id}: {w}' for w in n.provenance.warnings]
            if n.provenance.confidence < .8:
                result.append(f'{n.id}: low confidence; content retained')
            if n.provenance.text_alignment != 'verified':
                result.append(f'{n.id}: draft/source text {n.provenance.text_alignment}')
        return result


def digest(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode='json')
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False, default=lambda o: o.model_dump(mode='json') if isinstance(o, BaseModel) else str(o)).encode()).hexdigest()


def load_page(data):
    """Unknown versions fail explicitly, never guess a forward migration."""
    if data.get('schema_version') != '1.0':
        raise ValueError('unsupported semantic schema_version')
    return Page.model_validate(data)


def correct_node(page, object_id, replacement, revision, reason):
    """Replace one reviewed node, retaining immutable correction provenance."""
    data = page.model_dump(mode='json')
    original = next(n for n in page.nodes if n.id == object_id)
    if replacement.id != object_id:
        raise ValueError('correction must retain stable object ID')
    data['nodes'] = [replacement.model_dump(mode='json') if n.id == object_id else n.model_dump(mode='json') for n in page.nodes]
    data['revision'] = revision
    data['corrections'].append(Correction(revision=revision, object_id=object_id, reason=reason, before_sha256=digest(original), after_sha256=digest(replacement)).model_dump())
    return load_page(data)
