"""add visual strategy to projects

Revision ID: 023_visual_strategy
Revises: 022_user_credits
Create Date: 2026-06-27 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '023_visual_strategy'
down_revision = '022_user_credits'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = inspect(op.get_bind()).get_columns(table_name)
    return any(column['name'] == column_name for column in columns)


def upgrade() -> None:
    if not _column_exists('projects', 'visual_strategy'):
        op.add_column(
            'projects',
            sa.Column('visual_strategy', sa.String(length=30), nullable=False, server_default='native'),
        )
    if not _column_exists('projects', 'external_style_skill_id'):
        op.add_column('projects', sa.Column('external_style_skill_id', sa.String(length=128), nullable=True))
    if not _column_exists('projects', 'external_style_payload'):
        op.add_column('projects', sa.Column('external_style_payload', sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists('projects', 'external_style_payload'):
        op.drop_column('projects', 'external_style_payload')
    if _column_exists('projects', 'external_style_skill_id'):
        op.drop_column('projects', 'external_style_skill_id')
    if _column_exists('projects', 'visual_strategy'):
        op.drop_column('projects', 'visual_strategy')
