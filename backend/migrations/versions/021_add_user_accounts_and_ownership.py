"""add user accounts and ownership columns

Revision ID: 021_user_accounts
Revises: 020_add_mineru_provider
Create Date: 2026-06-20 00:00:00.000000

"""
import uuid
import secrets

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash


revision = '021_user_accounts'
down_revision = '020_add_mineru_provider'
branch_labels = None
depends_on = None


OWNER_TABLES = (
    'projects',
    'settings',
    'user_templates',
    'user_style_templates',
    'reference_files',
    'materials',
    'tasks',
)


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    columns = [col['name'] for col in inspect(op.get_bind()).get_columns(table_name)]
    return column_name in columns


def _ensure_default_user() -> str:
    bind = op.get_bind()
    row = bind.execute(sa.text("SELECT id FROM users WHERE username = :username"), {"username": "admin"}).fetchone()
    if row:
        return row[0]

    user_id = str(uuid.uuid4())
    bind.execute(
        sa.text(
            """
            INSERT INTO users (id, username, email, password_hash, is_active, created_at, updated_at)
            VALUES (:id, :username, NULL, :password_hash, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        ),
        {
            "id": user_id,
            "username": "admin",
            # A migrated owner is needed for legacy rows, but a migration must
            # never create a remotely usable, shared credential.
            "password_hash": generate_password_hash(secrets.token_urlsafe(48)),
        },
    )
    return user_id


def upgrade() -> None:
    if not _table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('username', sa.String(length=80), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username'),
            sa.UniqueConstraint('email'),
        )
        op.create_index('ix_users_username', 'users', ['username'])
        op.create_index('ix_users_email', 'users', ['email'])

    default_user_id = _ensure_default_user()

    for table_name in OWNER_TABLES:
        if not _table_exists(table_name):
            continue
        if not _column_exists(table_name, 'user_id'):
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
                batch_op.create_index(f'ix_{table_name}_user_id', ['user_id'])
        op.execute(
            sa.text(f"UPDATE {table_name} SET user_id = :user_id WHERE user_id IS NULL")
            .bindparams(user_id=default_user_id)
        )


def downgrade() -> None:
    for table_name in reversed(OWNER_TABLES):
        if not _column_exists(table_name, 'user_id'):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            try:
                batch_op.drop_index(f'ix_{table_name}_user_id')
            except Exception:
                pass
            batch_op.drop_column('user_id')

    if _table_exists('users'):
        op.drop_index('ix_users_email', table_name='users')
        op.drop_index('ix_users_username', table_name='users')
        op.drop_table('users')
