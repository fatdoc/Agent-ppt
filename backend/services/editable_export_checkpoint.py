"""Durable, project-local checkpoints for expensive editable-export stages.

Only complete stages are published. Assets are copied out of temporary provider
directories before an atomic manifest replacement, so a process restart is safe.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from services.image_editability.data_models import BBox, EditableElement, EditableImage
from services.image_editability.text_attribute_extractors import TextStyleResult

PATH_FIELDS = {'image_path', 'clean_background', 'inpainted_background_path'}


def digest_file(path):
    with open(path, 'rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        return digest.hexdigest()


def _element(data):
    return EditableElement(**{
        **data,
        'bbox': BBox(**data['bbox']),
        'bbox_global': BBox(**data['bbox_global']),
        'children': [_element(child) for child in data['children']],
    })


class EditableExportCheckpoint:
    VERSION = 1

    def __init__(self, directory, settings):
        self.directory = Path(directory)
        self.settings = settings

    def key(self, image_path):
        payload = [self.VERSION, str(Path(image_path).resolve()), digest_file(image_path), self.settings]
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def _read(self, key):
        return json.loads((self.directory / key / 'checkpoint.json').read_text())

    @staticmethod
    def _publish(path, data):
        fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load_analysis(self, key):
        try:
            record = self._read(key)
            root = (self.directory / key).resolve()
            for relative, expected in record['assets'].items():
                asset = (root / relative).resolve()
                if not asset.is_relative_to(root) or digest_file(asset) != expected:
                    return None

            def restore(data):
                for name, value in data.items():
                    if name in PATH_FIELDS and value:
                        if value not in record['assets']:
                            raise ValueError('Untracked checkpoint asset')
                        data[name] = str(root / value)
                for child in data.get('elements', data.get('children', [])):
                    restore(child)

            data = record['analysis']
            restore(data)
            data['elements'] = [_element(item) for item in data['elements']]
            return EditableImage(**data)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def save_analysis(self, key, result):
        root = self.directory / key
        root.mkdir(parents=True, exist_ok=True)
        # Each concurrent writer owns its assets; only the manifest is replaced.
        assets_dir = Path(tempfile.mkdtemp(prefix='assets-', dir=root))
        assets = {}
        copied = {}
        data = result.to_dict()

        def preserve(item):
            for name, value in item.items():
                if name in PATH_FIELDS and value:
                    if value not in copied:
                        target = assets_dir / f'{len(copied)}{Path(value).suffix}'
                        shutil.copyfile(value, target)
                        relative = str(target.relative_to(root))
                        copied[value] = relative
                        assets[relative] = digest_file(target)
                    item[name] = copied[value]
            for child in item.get('elements', item.get('children', [])):
                preserve(child)

        try:
            preserve(data)
            self._publish(root / 'checkpoint.json', {'analysis': data, 'assets': assets})
        except Exception:
            shutil.rmtree(assets_dir, ignore_errors=True)
            raise

    def load_styles(self, key, image_id):
        try:
            record = json.loads((self.directory / key / f'styles-{image_id}.json').read_text())
            return {name: TextStyleResult.from_dict(value) for name, value in record.items()}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def save_styles(self, key, image_id, styles):
        root = self.directory / key
        root.mkdir(parents=True, exist_ok=True)
        self._publish(root / f'styles-{image_id}.json', {
            name: value.to_dict() for name, value in styles.items()
        })


def provider_signature(ai_service):
    """Fingerprint model/routing identity without persisting credentials."""
    identity = {}
    for role in ('caption', 'image'):
        provider = getattr(ai_service, f'{role}_provider', None)
        client = getattr(provider, 'client', None)
        identity[role] = [
            type(provider).__module__, type(provider).__name__,
            getattr(ai_service, f'{role}_model', None),
            str(getattr(provider, 'api_base', getattr(client, 'base_url', ''))),
        ]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
