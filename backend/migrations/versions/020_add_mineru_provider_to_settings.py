"""add mineru provider to settings

Revision ID: 020_add_mineru_provider
Revises: 019_add_ppt_to_ppt_blueprint
Create Date: 2026-06-01 08:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = '020_add_mineru_provider'
down_revision = '019_add_ppt_to_ppt_blueprint'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('settings', 'mineru_provider'):
        op.add_column('settings', sa.Column('mineru_provider', sa.String(length=20), nullable=True))


def downgrade() -> None:
    if _column_exists('settings', 'mineru_provider'):
        op.drop_column('settings', 'mineru_provider')
