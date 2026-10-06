"""add per-page template system

Revision ID: 019_per_page_template
Revises: 018_add_project_title
"""
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import op


revision = '019_per_page_template'
down_revision = '018_add_project_title'
branch_labels = None
depends_on = None
logger = logging.getLogger(__name__)


def upgrade():
    with op.batch_alter_table('projects') as batch_op:
        batch_op.add_column(sa.Column('template_mode', sa.String(length=10), nullable=False, server_default='single'))

    op.create_table(
        'project_template_assets',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('image_path', sa.String(length=500), nullable=False),
        sa.Column('thumb_path', sa.String(length=500), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='upload'),
        sa.Column('source_pdf_id', sa.String(length=36), nullable=True),
        sa.Column('source_page_index', sa.Integer(), nullable=True),
        sa.Column('analysis_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('analysis_json', sa.Text(), nullable=True),
        sa.Column('analysis_notes', sa.Text(), nullable=True),
        sa.Column('analysis_error', sa.Text(), nullable=True),
        sa.Column('user_label', sa.String(length=200), nullable=True),
        sa.Column('user_edited_analysis', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_project_template_assets_project_id', 'project_template_assets', ['project_id'])

    with op.batch_alter_table('pages') as batch_op:
        batch_op.add_column(sa.Column('template_asset_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('template_style_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('template_selection_source', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('template_match_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('template_match_confidence', sa.Float(), nullable=True))
        batch_op.create_foreign_key(
            'fk_pages_template_asset_id',
            'project_template_assets',
            ['template_asset_id'],
            ['id'],
            ondelete='SET NULL',
        )
        batch_op.create_index('ix_pages_template_asset_id', ['template_asset_id'])

    bind = op.get_bind()
    upload_root = os.environ.get('UPLOAD_FOLDER') or str(Path(__file__).resolve().parents[3] / 'uploads')
    projects = bind.execute(sa.text(
        'SELECT id, template_image_path, template_style FROM projects '
        'WHERE template_image_path IS NOT NULL OR template_style IS NOT NULL'
    )).fetchall()
    now = datetime.utcnow()
    for project_id, template_path, template_style in projects:
        asset_id = None
        if template_path:
            absolute_path = template_path if os.path.isabs(template_path) else os.path.join(upload_root, template_path)
            if os.path.exists(absolute_path):
                asset_id = str(uuid.uuid4())
                bind.execute(sa.text(
                    'INSERT INTO project_template_assets '
                    '(id, project_id, image_path, source, analysis_status, user_edited_analysis, sort_order, created_at, updated_at) '
                    'VALUES (:id, :project_id, :image_path, :source, :status, 0, 0, :now, :now)'
                ), {
                    'id': asset_id,
                    'project_id': project_id,
                    'image_path': template_path,
                    'source': 'upload',
                    'status': 'pending',
                    'now': now,
                })
            else:
                logger.warning('Template file missing for project %s: %s', project_id, template_path)

        if asset_id or template_style:
            bind.execute(sa.text(
                'UPDATE pages SET template_asset_id = COALESCE(:asset_id, template_asset_id), '
                'template_style_text = COALESCE(:template_style, template_style_text), '
                'template_selection_source = :source WHERE project_id = :project_id'
            ), {
                'asset_id': asset_id,
                'template_style': template_style,
                'source': 'batch_apply',
                'project_id': project_id,
            })


def downgrade():
    with op.batch_alter_table('pages') as batch_op:
        batch_op.drop_index('ix_pages_template_asset_id')
        batch_op.drop_constraint('fk_pages_template_asset_id', type_='foreignkey')
        batch_op.drop_column('template_match_confidence')
        batch_op.drop_column('template_match_reason')
        batch_op.drop_column('template_selection_source')
        batch_op.drop_column('template_style_text')
        batch_op.drop_column('template_asset_id')
    op.drop_index('ix_project_template_assets_project_id', table_name='project_template_assets')
    op.drop_table('project_template_assets')
    with op.batch_alter_table('projects') as batch_op:
        batch_op.drop_column('template_mode')
