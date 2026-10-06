"""Server-selected, authorized project scope; never trust client-supplied roots."""
import hashlib
from pathlib import Path
from io import BytesIO
from PIL import Image
from lxml import etree
from .model import Asset


class AssetStore:
    def __init__(self, root, *, user_id, project_id):
        self.root = Path(root).resolve(strict=True)
        self.user_id, self.project_id = user_id, project_id

    def read(self, asset: Asset):
        if (asset.user_id, asset.project_id) != (self.user_id, self.project_id):
            raise ValueError('cross-project asset access')
        path = (self.root / asset.uri).resolve(strict=True)
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError('asset escapes authorized root')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != asset.sha256:
            raise ValueError('asset content hash mismatch')
        if asset.media_type == 'image/svg+xml':
            root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True))
            if root.getroottree().docinfo.doctype:
                raise ValueError('SVG DTD forbidden')
            if etree.QName(root).localname != 'svg':
                raise ValueError('not SVG')
            for el in root.iter():
                if not isinstance(el.tag, str):
                    continue
                if etree.QName(el).localname in ('script', 'foreignObject', 'style'):
                    raise ValueError('active SVG forbidden')
                for key, value in el.attrib.items():
                    if key.lower().startswith('on') or ('href' in key and not value.startswith('#')) or 'url(' in value.lower():
                        raise ValueError('external or active SVG resource forbidden')
        return raw

    def verify(self, page):
        if (page.user_id, page.project_id) != (self.user_id, self.project_id):
            raise ValueError('page outside authorized scope')
        blobs = {asset.id: self.read(asset) for asset in page.assets}
        for node in page.nodes:
            if node.picture and node.picture.preserve_whole:
                with Image.open(BytesIO(blobs[node.picture.asset_id])) as im:
                    if abs((node.box.w/node.box.h)/(im.width/im.height)-1) > .03:
                        raise ValueError('whole screenshot aspect ratio changed')
