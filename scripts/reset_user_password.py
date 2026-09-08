#!/usr/bin/env python3
"""Reset one local account without importing the Flask app or loading .env."""
from __future__ import annotations

import argparse
import getpass
import os

import sqlalchemy as sa
from werkzeug.security import generate_password_hash


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Reset a Banana Slides password and revoke existing sessions.',
    )
    parser.add_argument('username')
    parser.add_argument(
        '--database-url',
        default=os.environ.get('DATABASE_URL'),
        help='Explicit SQLAlchemy database URL (or set DATABASE_URL).',
    )
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if not args.database_url:
        raise SystemExit('DATABASE_URL or --database-url is required; .env is not loaded')

    password = getpass.getpass('New password: ')
    confirmation = getpass.getpass('Confirm password: ')
    if password != confirmation:
        raise SystemExit('Passwords do not match')
    if len(password) < 10:
        raise SystemExit('Password must contain at least 10 characters')

    engine = sa.create_engine(args.database_url)
    with engine.begin() as connection:
        result = connection.execute(
            sa.text(
                'UPDATE users '
                'SET password_hash = :password_hash, '
                'password_reset_required = :reset_required, '
                'auth_version = auth_version + 1, '
                'updated_at = CURRENT_TIMESTAMP '
                'WHERE username = :username'
            ),
            {
                'password_hash': generate_password_hash(password),
                'reset_required': False,
                'username': args.username,
            },
        )
        if result.rowcount != 1:
            raise SystemExit(f'User not found: {args.username}')

    print(f'Password reset completed for {args.username}; existing sessions were revoked.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
