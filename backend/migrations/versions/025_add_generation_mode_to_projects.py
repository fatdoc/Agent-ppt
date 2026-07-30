"""add generation mode to projects

Revision ID: 025_generation_mode
Revises: 024_agent_mode_v1
Create Date: 2026-06-29 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '025_generation_mode'
down_revision = '024_agent_mode_v1'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = inspect(op.get_bind()).get_columns(table_name)
    return any(column['name'] == column_name for column in columns)


def upgrade() -> None:
    if not _column_exists('projects', 'generation_mode'):
        op.add_column(
            'projects',
            sa.Column('generation_mode', sa.String(length=30), nullable=False, server_default='fast'),
        )
    if not _column_exists('projects', 'harness_template'):
        op.add_column('projects', sa.Column('harness_template', sa.String(length=80), nullable=True))
    if not _column_exists('projects', 'harness_payload'):
        op.add_column('projects', sa.Column('harness_payload', sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists('projects', 'harness_payload'):
        op.drop_column('projects', 'harness_payload')
    if _column_exists('projects', 'harness_template'):
        op.drop_column('projects', 'harness_template')
    if _column_exists('projects', 'generation_mode'):
        op.drop_column('projects', 'generation_mode')
