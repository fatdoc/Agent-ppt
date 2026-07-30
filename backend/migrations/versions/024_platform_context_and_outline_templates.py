"""add platform context and outline templates

Revision ID: 024_platform_refactor
Revises: 023_harness_generation_mode
Create Date: 2026-07-30 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '024_platform_refactor'
down_revision = '023_harness_generation_mode'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    return column_name in {
        column['name']
        for column in inspect(op.get_bind()).get_columns(table_name)
    }


def upgrade() -> None:
    if not _column_exists('projects', 'platform_context'):
        op.add_column('projects', sa.Column('platform_context', sa.Text(), nullable=True))
    if not _column_exists('projects', 'outline_template_id'):
        op.add_column('projects', sa.Column('outline_template_id', sa.String(length=36), nullable=True))
        op.create_index('ix_projects_outline_template_id', 'projects', ['outline_template_id'])
    if not _column_exists('projects', 'ppt_template_id'):
        op.add_column('projects', sa.Column('ppt_template_id', sa.String(length=36), nullable=True))

    op.create_table(
        'outline_templates',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('competition_id', sa.String(length=80), nullable=True),
        sa.Column('competition_type_id', sa.String(length=80), nullable=True),
        sa.Column('track_id', sa.String(length=80), nullable=True),
        sa.Column('theme_id', sa.String(length=80), nullable=True),
        sa.Column('support_scope', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('target_page_count', sa.Integer(), nullable=True),
        sa.Column('style_tags', sa.Text(), nullable=True),
        sa.Column('sections', sa.Text(), nullable=False),
        sa.Column('versions', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_outline_templates_user_id', 'outline_templates', ['user_id'])
    op.create_index('ix_outline_templates_competition_id', 'outline_templates', ['competition_id'])
    op.create_index('ix_outline_templates_status', 'outline_templates', ['status'])


def downgrade() -> None:
    op.drop_index('ix_outline_templates_status', table_name='outline_templates')
    op.drop_index('ix_outline_templates_competition_id', table_name='outline_templates')
    op.drop_index('ix_outline_templates_user_id', table_name='outline_templates')
    op.drop_table('outline_templates')
    if _column_exists('projects', 'ppt_template_id'):
        op.drop_column('projects', 'ppt_template_id')
    if _column_exists('projects', 'outline_template_id'):
        op.drop_index('ix_projects_outline_template_id', table_name='projects')
        op.drop_column('projects', 'outline_template_id')
    if _column_exists('projects', 'platform_context'):
        op.drop_column('projects', 'platform_context')
