"""add ppt_to_ppt_blueprint to projects

Revision ID: 019_add_ppt_to_ppt_blueprint
Revises: 018_add_project_title
Create Date: 2026-05-23
"""
from alembic import op
import sqlalchemy as sa


revision = '019_add_ppt_to_ppt_blueprint'
down_revision = '018_add_project_title'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('projects', sa.Column('ppt_to_ppt_blueprint', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('projects', 'ppt_to_ppt_blueprint')
