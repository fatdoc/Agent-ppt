"""Add isolated education workflow tables; existing projects are unchanged."""

from alembic import op
import sqlalchemy as sa

revision = "032_competition_education"
down_revision = "031_pptist_editor_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "competition_documents",
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("active_task_id", sa.String(36)),
    )
    op.create_table(
        "competition_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "revision", name="uq_competition_revision"),
    )
    op.create_table(
        "competition_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_key", sa.String(80), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.UniqueConstraint(
            "project_id", "request_key", name="uq_competition_operation"
        ),
    )


def downgrade():
    op.drop_table("competition_operations")
    op.drop_table("competition_revisions")
    op.drop_table("competition_documents")
