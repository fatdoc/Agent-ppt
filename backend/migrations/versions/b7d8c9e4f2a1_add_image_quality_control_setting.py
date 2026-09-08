"""add image quality control setting

Revision ID: b7d8c9e4f2a1
Revises: 018_add_project_title
"""
import sqlalchemy as sa
from alembic import op


revision = 'b7d8c9e4f2a1'
down_revision = '018_add_project_title'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('settings', sa.Column(
        'enable_image_quality_control',
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ))


def downgrade():
    op.drop_column('settings', 'enable_image_quality_control')
