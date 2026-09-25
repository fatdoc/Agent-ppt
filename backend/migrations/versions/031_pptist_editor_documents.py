"""Add immutable editor documents; never modify Local Pages or legacy exports."""
from alembic import op
import sqlalchemy as sa
revision = '031_pptist_editor_documents'
down_revision = '030_batch01_safety_expand'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('editor_documents',
        sa.Column('project_id',sa.String(36),sa.ForeignKey('projects.id'),primary_key=True),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.CheckConstraint('revision > 0',name='ck_editor_document_revision_positive'))
    op.create_table('editor_revisions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('project_id',sa.String(36),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('actor_user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('restored_from_revision',sa.Integer(),nullable=True),
        sa.CheckConstraint('revision > 0',name='ck_editor_revision_positive'),
        sa.Column('payload',sa.Text(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.UniqueConstraint('project_id','revision',name='uq_editor_project_revision'))

def downgrade():
    op.drop_table('editor_revisions')
    op.drop_table('editor_documents')
