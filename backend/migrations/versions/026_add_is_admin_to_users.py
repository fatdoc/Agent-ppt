"""add is_admin to users

Revision ID: 026_user_is_admin
Revises: 025_generation_mode
Create Date: 2026-07-08 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '026_user_is_admin'
down_revision = '025_generation_mode'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = [col['name'] for col in inspect(op.get_bind()).get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('users', 'is_admin'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('0')))

    op.execute(sa.text("UPDATE users SET is_admin = 1 WHERE username = 'admin'"))


def downgrade() -> None:
    if _column_exists('users', 'is_admin'):
        with op.batch_alter_table('users') as batch_op:
            batch_op.drop_column('is_admin')
