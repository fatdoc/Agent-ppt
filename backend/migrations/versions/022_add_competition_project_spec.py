"""add competition project spec

Revision ID: 022_competition_project_spec
Revises: 021_user_accounts
Create Date: 2026-06-25 12:10:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '022_competition_project_spec'
down_revision = '021_user_accounts'
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    columns = [col['name'] for col in inspect(op.get_bind()).get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists('projects', 'competition_project_spec'):
        op.add_column('projects', sa.Column('competition_project_spec', sa.Text(), nullable=True))


def downgrade() -> None:
    if _column_exists('projects', 'competition_project_spec'):
        op.drop_column('projects', 'competition_project_spec')
