"""Add reversible education space organization."""

from alembic import op
import sqlalchemy as sa

revision = "033_education_space"
down_revision = "032_competition_education"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "education_space_entries",
        sa.Column("key", sa.String(90), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("previous_category", sa.String(20)),
        sa.Column("display_name", sa.String(500)),
        sa.Column("deleted_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_education_space_entries_user_id", "education_space_entries", ["user_id"]
    )


def downgrade():
    op.drop_table("education_space_entries")
