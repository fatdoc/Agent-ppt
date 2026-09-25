"""Audit actual OOXML, including all leaves inside nested groups."""
import hashlib
import posixpath
from io import BytesIO
from zipfile import ZipFile
from lxml import etree as E
from .builder import EMU

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
SHAPES = {'sp', 'pic', 'graphicFrame', 'grpSp'}


def audit_pptx(raw, pages):
    reports = []
    def require(condition, message):
        if not condition:
            raise ValueError('PPTX audit: '+message)
    with ZipFile(BytesIO(raw)) as z:
        require(z.testzip() is None, 'corrupt package')
        names = set(z.namelist())
        source_hashes = {p.source.sha256 for p in pages}
        for path in names:
            if path.startswith('ppt/media/'):
                require(hashlib.sha256(z.read(path)).hexdigest() not in source_hashes, 'embedded full source image')
            if path.endswith('.rels'):
                rels = E.fromstring(z.read(path))
                base = posixpath.dirname(posixpath.dirname(path))
                ids = [r.get('Id') for r in rels]
                require(len(ids) == len(set(ids)), 'duplicate relationship ID')
                for rel in rels:
                    require(rel.get('TargetMode') != 'External', 'external relationship')
                    target = rel.get('Target')
                    resolved = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(base, target))
                    require(resolved in names, 'broken resource relationship '+resolved)
        presentation = E.fromstring(z.read('ppt/presentation.xml'))
        require(len(presentation.findall('p:sldIdLst/p:sldId', NS)) == len(pages), 'slide count')
        for i, page in enumerate(pages, 1):
            root = E.fromstring(z.read(f'ppt/slides/slide{i}.xml'))
            require(not root.findall('.//p:bg//a:blip', NS), 'image background forbidden')
            ids = [n.get('id') for n in root.findall('.//p:cNvPr', NS)]
            require(len(ids) == len(set(ids)), 'duplicate OOXML object ID')
            tree = root.find('p:cSld/p:spTree', NS)
            actual, parents, groups = {}, {}, {}
            order = []
            def walk(container, parent=None):
                for el in container:
                    kind = E.QName(el).localname
                    if kind not in SHAPES:
                        continue
                    name = el.find('.//p:cNvPr', NS).get('name').split('::', 1)[0]
                    require(name not in actual and name not in groups, 'duplicate stable object ID')
                    parents[name] = parent
                    if kind == 'grpSp':
                        groups[name] = el
                        xf = el.find('p:grpSpPr/a:xfrm', NS)
                        require(xf is not None and xf.find('a:off', NS).attrib == xf.find('a:chOff', NS).attrib and xf.find('a:ext', NS).attrib == xf.find('a:chExt', NS).attrib, 'group coordinate transform changed')
                        require(not xf.get('rot') and not xf.get('flipH') and not xf.get('flipV'), 'non-identity group')
                        walk(el, name)
                    else:
                        actual[name] = el
                        order.append(name)
            walk(tree)
            require(order == [n.id for n in sorted(page.nodes, key=lambda n: n.layer)], 'group changed leaf layer order')
            require(set(groups) == {g.id for g in page.groups}, 'group IDs')
            require(set(actual) == {n.id for n in page.nodes}, 'leaf IDs/count')
            for item in page.nodes+page.groups:
                require(parents[item.id] == item.parent_id, 'wrong group parent')
            for node in page.nodes:
                el = actual[node.id]
                xf = el.find('p:spPr/a:xfrm', NS)
                if xf is None:
                    xf = el.find('p:xfrm', NS)
                off, ext = xf.find('a:off', NS), xf.find('a:ext', NS)
                got = [int(off.get('x')), int(off.get('y')), int(ext.get('cx')), int(ext.get('cy'))]
                expected = [round(v*EMU) for v in (node.box.x, node.box.y, node.box.w, node.box.h)]
                require(all(abs(a-b) <= 1 for a, b in zip(got, expected)), node.id+' coordinate drift')
                require(abs((int(xf.get('rot', '0'))/60000-node.rotation) % 360) < .001, node.id+' rotation')
                if node.kind == 'text':
                    got_text = [''.join(p.xpath('a:r/a:t/text()', namespaces=NS)) for p in el.findall('p:txBody/a:p', NS)]
                    require(got_text == [''.join(r.text for r in p.runs) for p in node.text.paragraphs], node.id+' text changed')
                elif node.kind == 'table':
                    got_rows = [[''.join(c.xpath('.//a:t/text()', namespaces=NS)) for c in row.findall('a:tc', NS)] for row in el.findall('.//a:tbl/a:tr', NS)]
                    require(got_rows == node.table.rows, node.id+' table changed')
                elif node.kind == 'shape':
                    require(el.find('p:spPr/a:prstGeom', NS).get('prst') == node.shape.geometry, node.id+' fragmented/wrong shape')
                elif node.kind == 'svg':
                    require(bool(el.xpath('.//*[local-name()="svgBlip"]')), node.id+' missing SVG source')
            # Verify every referenced raster/SVG is exactly the declared asset.
            rels = E.fromstring(z.read(f'ppt/slides/_rels/slide{i}.xml.rels'))
            mapping = {r.get('Id'): posixpath.normpath(posixpath.join('ppt/slides', r.get('Target'))) for r in rels}
            assets = {a.id: a for a in page.assets}
            for node in page.nodes:
                if node.picture:
                    el = actual[node.id]
                    blip = el.find('.//a:blip', NS)
                    asset_id = node.picture.fallback_asset_id if node.kind == 'svg' else node.picture.asset_id
                    rid = blip.get('{'+NS['r']+'}embed')
                    require(hashlib.sha256(z.read(mapping[rid])).hexdigest() == assets[asset_id].sha256, 'wrong raster asset')
                    crop = el.find('.//a:srcRect', NS)
                    for key, attr in [('left', 'l'), ('top', 't'), ('right', 'r'), ('bottom', 'b')]:
                        require(abs(int(crop.get(attr, '0'))/100000-getattr(node.picture.crop, key)) <= .00001 if crop is not None else getattr(node.picture.crop, key) == 0, 'crop changed')
                    if node.kind == 'svg':
                        rid = el.xpath('.//*[local-name()="svgBlip"]')[0].get('{'+NS['r']+'}embed')
                        require(hashlib.sha256(z.read(mapping[rid])).hexdigest() == assets[node.picture.asset_id].sha256, 'wrong SVG source')
            counts = {kind: sum(n.kind == kind for n in page.nodes) for kind in ('text', 'shape', 'image', 'svg', 'table')}
            reports.append(dict(page_id=page.id, leaf_objects=len(actual), groups=len(groups), counts=counts, warnings=page.issues(), structure='passed', render='not_run', client='not_run'))
    return reports
