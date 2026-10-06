"""add public PPT API keys and generation jobs

Revision ID: 027_public_ppt_api
Revises: 026_user_is_admin
Create Date: 2026-07-23 10:10:00.000000

"""
import sqlalchemy as sa
from alembic import op


revision = "027_public_ppt_api"
down_revision = "026_user_is_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=40), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes_json", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
        sa.UniqueConstraint("key_prefix"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])

    op.create_table(
        "public_ppt_generations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("api_key_id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("description_task_id", sa.String(length=36), nullable=False),
        sa.Column("image_task_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("current_stage", sa.String(length=40), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"]),
        sa.ForeignKeyConstraint(["description_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["image_task_id"], ["tasks.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
        sa.UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_public_ppt_generation_idempotency",
        ),
    )
    op.create_index("ix_public_ppt_generations_user_id", "public_ppt_generations", ["user_id"])
    op.create_index("ix_public_ppt_generations_api_key_id", "public_ppt_generations", ["api_key_id"])
    op.create_index("ix_public_ppt_generations_project_id", "public_ppt_generations", ["project_id"])
    op.create_index("ix_public_ppt_generations_status", "public_ppt_generations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_public_ppt_generations_status", table_name="public_ppt_generations")
    op.drop_index("ix_public_ppt_generations_project_id", table_name="public_ppt_generations")
    op.drop_index("ix_public_ppt_generations_api_key_id", table_name="public_ppt_generations")
    op.drop_index("ix_public_ppt_generations_user_id", table_name="public_ppt_generations")
    op.drop_table("public_ppt_generations")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
