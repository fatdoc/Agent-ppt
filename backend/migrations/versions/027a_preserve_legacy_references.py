"""add expand-only slots for preserving legacy references

Revision ID: 027a_legacy_references
Revises: 027_public_ppt_api
"""
import sqlalchemy as sa
from alembic import op


revision = '027a_legacy_references'
down_revision = '027_public_ppt_api'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some historical SQLite installations ran with foreign-key enforcement
    # disabled. This revision is deliberately schema-only: the audited repair
    # workflow decides whether each orphan is recoverable before it copies the
    # identifier to legacy_* and clears the canonical foreign-key column.
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('legacy_project_id', sa.String(length=36), nullable=True))
        batch_op.alter_column(
            'project_id',
            existing_type=sa.String(length=36),
            nullable=True,
        )
        batch_op.create_index('ix_tasks_legacy_project_id', ['legacy_project_id'])

    with op.batch_alter_table('credit_ledger') as batch_op:
        batch_op.add_column(sa.Column('legacy_project_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('legacy_task_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_credit_ledger_legacy_project_id', ['legacy_project_id'])
        batch_op.create_index('ix_credit_ledger_legacy_task_id', ['legacy_task_id'])

    with op.batch_alter_table('agent_runs') as batch_op:
        batch_op.add_column(sa.Column('legacy_project_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_agent_runs_legacy_project_id', ['legacy_project_id'])


def downgrade() -> None:
    bind = op.get_bind()
    preserved_references = bind.execute(sa.text(
        'SELECT '
        ' (SELECT COUNT(*) FROM tasks WHERE legacy_project_id IS NOT NULL) + '
        ' (SELECT COUNT(*) FROM credit_ledger '
        '  WHERE legacy_project_id IS NOT NULL OR legacy_task_id IS NOT NULL) + '
        ' (SELECT COUNT(*) FROM agent_runs WHERE legacy_project_id IS NOT NULL)'
    )).scalar_one()
    if preserved_references:
        raise RuntimeError(
            'Cannot downgrade 027a_legacy_references: '
            f'{preserved_references} preserved legacy reference(s) would be lost'
        )

    unresolved_tasks = bind.execute(sa.text(
        'SELECT COUNT(*) FROM tasks WHERE project_id IS NULL'
    )).scalar_one()
    if unresolved_tasks:
        raise RuntimeError(
            'Cannot downgrade 027a_legacy_references: '
            f'{unresolved_tasks} task(s) have no canonical project reference'
        )

    with op.batch_alter_table('agent_runs') as batch_op:
        batch_op.drop_index('ix_agent_runs_legacy_project_id')
        batch_op.drop_column('legacy_project_id')

    with op.batch_alter_table('credit_ledger') as batch_op:
        batch_op.drop_index('ix_credit_ledger_legacy_task_id')
        batch_op.drop_index('ix_credit_ledger_legacy_project_id')
        batch_op.drop_column('legacy_task_id')
        batch_op.drop_column('legacy_project_id')

    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_index('ix_tasks_legacy_project_id')
        batch_op.drop_column('legacy_project_id')
        batch_op.alter_column(
            'project_id',
            existing_type=sa.String(length=36),
            nullable=False,
        )
