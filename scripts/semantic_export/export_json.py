"""Rebuild a reviewed semantic JSON deck, offline and without its original PPT.

This local CLI treats --asset-root as a trusted operator-selected directory;
HTTP integrations must derive that root from authenticated project ownership.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'backend'))
from services.semantic_export import AssetStore, export_pages, load_page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('pages', type=Path, nargs='+', help='Page JSON files in slide order')
    parser.add_argument('--asset-root', type=Path, required=True)
    parser.add_argument('--user-id', required=True)
    parser.add_argument('--project-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pages = [load_page(json.loads(path.read_text())) for path in args.pages]
    store = AssetStore(args.asset_root, user_id=args.user_id, project_id=args.project_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw, report = export_pages(pages, store=store,
                              checkpoint_dir=args.output.parent/'.semantic-checkpoints', mode='semantic')
    fd, temp = tempfile.mkstemp(dir=args.output.parent, suffix='.pptx.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, args.output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    args.output.with_suffix('.audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(args.output)


if __name__ == '__main__':
    main()
