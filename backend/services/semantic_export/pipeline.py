"""Offline-capable page stages. Reuses legacy atomic checkpoint publication.

The caller owns authorization, task lifecycle, settlement and configuration
capture. Pure progress events contain no credentials and do not touch a DB.
"""
from dataclasses import dataclass
from typing import Callable
import base64
import json
from pathlib import Path
from services.editable_export_checkpoint import EditableExportCheckpoint
from .model import Source, digest, load_page
from .builder import build_deck
from .audit import audit_pptx

STRATEGY = 'semantic-native-v1'


@dataclass(frozen=True)
class PageJob:
    id: str
    source: Source
    extraction_signature: str
    organization_signature: str
    correction_revision: str
    extract: Callable[[], dict]
    organize: Callable[[dict], dict]


class SemanticExportFailure(RuntimeError):
    def __init__(self, errors, completed):
        self.errors, self.completed = errors, completed
        super().__init__('semantic export failed; pages requiring correction: '+', '.join(errors))


class ExportInterrupted(RuntimeError):
    """Task cancellation/deadline/progress sink failures abort the entire run."""


class StageCache:
    def __init__(self, directory, scope):
        self.root = Path(directory) / digest(scope)
        self.root.mkdir(parents=True, exist_ok=True)

    def run(self, key, factory):
        path = self.root / (key+'.json')
        try:
            record = json.loads(path.read_text())
            if digest(record['payload']) == record['sha256']:
                return record['payload'], True
        except (OSError, ValueError, KeyError, TypeError):
            pass
        value = factory()  # failures are never published
        EditableExportCheckpoint._publish(path, {'payload': value, 'sha256': digest(value)})
        return value, False


def export_jobs(jobs, *, store, checkpoint_dir, mode, on_event=lambda event: None, check_cancelled=lambda: None):
    if mode != 'semantic':
        raise ValueError('explicit semantic mode required; legacy exports use ExportService')
    if len({j.id for j in jobs}) != len(jobs):
        raise ValueError('duplicate job ID')
    scope = dict(user_id=store.user_id, project_id=store.project_id)
    cache = StageCache(checkpoint_dir, scope)
    def signal(event):
        try:
            on_event(event)
        except Exception as exc:
            raise ExportInterrupted('task callback interrupted semantic export') from exc

    def checkpoint():
        try:
            check_cancelled()
        except Exception as exc:
            raise ExportInterrupted('task cancelled or deadline exceeded') from exc

    completed, errors, pages = [], {}, []
    for job in jobs:
        stage = 'extract'
        try:
            def run(stage_name, key, factory):
                checkpoint()
                value, hit = cache.run(key, factory)
                signal(dict(page_id=job.id, stage=stage_name, status='completed', cache_hit=hit))
                return value
            source_key = digest([scope, job.id, job.source, '1.0', STRATEGY, job.extraction_signature])
            extracted = run('extract', source_key, job.extract)
            stage = 'semantic'
            semantic_key = digest([source_key, digest(extracted), job.organization_signature, job.correction_revision])
            def organize():
                page = load_page(job.organize(extracted))
                store.verify(page)
                if page.id != job.id or page.source != job.source:
                    raise ValueError('job/source version mismatch')
                return page.model_dump(mode='json')
            page = load_page(run(stage, semantic_key, organize))
            if page.id != job.id or page.source != job.source:
                raise ValueError('cached source version mismatch')
            store.verify(page)  # hashes and tenant scope rechecked even on cache hit
            stage = 'objects'
            build_key = digest([semantic_key, digest(page), 'builder-v2'])
            encoded = run(stage, build_key, lambda: base64.b64encode(build_deck([page], store)).decode())
            raw = base64.b64decode(encoded, validate=True)
            stage = 'acceptance'
            audit_key = digest([build_key, digest(encoded), 'audit-v2'])
            run(stage, audit_key, lambda: audit_pptx(raw, [page]))
            pages.append(page)
            completed.append(job.id)
        except ExportInterrupted:
            raise
        except Exception as exc:
            errors[job.id] = {'stage': stage, 'error': str(exc), 'status': 'needs_correction'}
            signal(dict(page_id=job.id, stage=stage, status='failed', error=str(exc)))
    if errors:
        raise SemanticExportFailure(errors, completed)
    # Final packaging is inexpensive and deterministic in semantic content;
    # expensive extraction/organization and independent page builds resume above.
    checkpoint()
    raw = build_deck(pages, store)
    report = audit_pptx(raw, pages)
    return raw, report


def export_pages(pages, **kwargs):
    """Explicit structured/manual input route; no implied automatic OCR success."""
    jobs = []
    for page in pages:
        data = page.model_dump(mode='json')
        jobs.append(PageJob(page.id, page.source, digest(data), 'structured-input-v1', page.revision,
                            lambda d=data: d, lambda d: d))
    return export_jobs(jobs, **kwargs)
