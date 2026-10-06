#!/usr/bin/env python3
"""Replay ONE saved vision response offline; never import the app or call AI.

Example: python scripts/validate_editor_page.py --image page.png
  --diagnostic private-diagnostic.json --output /tmp/new-page-check
The output directory must not exist. It contains private assets, semantic JSON,
and a checked one-page PPTX for local inspection, never a live editor document.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from PIL import Image
from services.pptist_editor.generation import validate_response, GenerationError
from services.semantic_export import AssetStore, export_pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--diagnostic', type=Path)
    inputs.add_argument('--response', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    response_file = args.diagnostic or args.response
    if args.image.stat().st_size > 40 * 1024 * 1024 or response_file.stat().st_size > 8 * 1024 * 1024:
        parser.error('Input exceeds safe replay size limit')
    sha = hashlib.sha256(args.image.read_bytes()).hexdigest()
    raw = response_file.read_text(encoding='utf-8')
    if args.diagnostic:
        record = json.loads(raw)
        if record.get('source_sha256') != sha:
            parser.error('Diagnostic and image hashes do not match')
        raw = record.get('response')
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = dict(id='offline-page', sha256=sha, outline=None, description=None)
    try:
        with Image.open(args.image) as image:
            page = validate_response(raw, image, source=source, project_id='offline-project', user_id='offline-user', root=args.output)
        store = AssetStore(args.output, user_id='offline-user', project_id='offline-project')
        pptx, audit = export_pages([page], store=store, checkpoint_dir=args.output / 'checkpoints', mode='semantic')
        (args.output / 'page.json').write_text(page.model_dump_json(indent=2), encoding='utf-8')
        (args.output / 'page.pptx').write_bytes(pptx)
        result = dict(status='passed', objects=len(page.nodes), groups=len(page.groups), audit=audit,
                      provider_calls=0, database_writes=0, render='not_run', office_client='not_run')
    except GenerationError as exc:
        result = dict(status='failed', message=str(exc), issues=exc.issues, provider_calls=0, database_writes=0)
    (args.output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
