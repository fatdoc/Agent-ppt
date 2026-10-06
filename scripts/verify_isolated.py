#!/usr/bin/env python3
"""Run validation with a clean environment, disposable DB/HOME, and no dotenv.

Uses the invoking interpreter's dependencies. Never copies user data or credentials.
Examples: python scripts/verify_isolated.py backend
          python scripts/verify_isolated.py runtime
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['backend', 'runtime'])
    args, extra = parser.parse_known_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='banana-validation-') as tmp:
        env = {
            'PATH': os.environ.get('PATH', '/usr/bin:/bin'),
            'HOME': tmp,
            'TMPDIR': tmp,
            'LOAD_DOTENV': 'false',
            'DATABASE_URL': f'sqlite:///{tmp}/validation.db',
            'UPLOAD_FOLDER': f'{tmp}/uploads',
            'SECRET_KEY': 'offline-validation-only-not-a-production-secret',
            'BANANA_ISOLATED_VERIFICATION': '1',
            'PYTHONIOENCODING': 'utf-8',
        }
        if args.mode == 'backend':
            command = [sys.executable, '-m', 'pytest', 'backend/tests', '-q', '-rs', *extra]
        else:
            command = [sys.executable, str(root/'scripts/verify_provider_runtime.py')]
        return subprocess.call(command, cwd=root, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
