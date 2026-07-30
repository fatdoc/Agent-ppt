"""add harness generation mode

Revision ID: 023_harness_generation_mode
Revises: 022_competition_project_spec
Create Date: 2026-06-29 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '023_harness_generation_mode'
down_revision = '022_competition_project_spec'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = [col['name'] for col in inspect(op.get_bind()).get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('projects', 'generation_mode'):
        op.add_column('projects', sa.Column('generation_mode', sa.String(length=20), server_default='fast', nullable=False))
    if not _column_exists('projects', 'harness_template'):
        op.add_column('projects', sa.Column('harness_template', sa.String(length=50), nullable=True))


def downgrade() -> None:
    if _column_exists('projects', 'harness_template'):
        op.drop_column('projects', 'harness_template')
    if _column_exists('projects', 'generation_mode'):
        op.drop_column('projects', 'generation_mode')
