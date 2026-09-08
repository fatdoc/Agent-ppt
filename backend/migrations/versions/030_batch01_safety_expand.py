"""expand auth, credit and file-artifact safety schema

Revision ID: 030_batch01_safety_expand
Revises: 029_merge_local_upstream
"""
import sqlalchemy as sa
from alembic import op
from werkzeug.security import check_password_hash


revision = '030_batch01_safety_expand'
down_revision = '029_merge_local_upstream'
branch_labels = None
depends_on = None


def _assert_credit_preflight(bind) -> None:
    invalid_accounts = bind.execute(sa.text(
        'SELECT COUNT(*) FROM credit_accounts '
        'WHERE balance < 0 OR reserved_balance < 0 OR reserved_balance > balance'
    )).scalar_one()
    duplicate_entries = bind.execute(sa.text(
        'SELECT COUNT(*) FROM ('
        ' SELECT task_id, entry_type FROM credit_ledger'
        ' WHERE task_id IS NOT NULL AND entry_type IN (\'reserve\', \'debit\', \'release\')'
        ' GROUP BY task_id, entry_type HAVING COUNT(*) > 1'
        ') AS duplicates'
    )).scalar_one()
    if invalid_accounts or duplicate_entries:
        raise RuntimeError(
            'Credit preflight failed: '
            f'invalid_accounts={invalid_accounts}, duplicate_task_entries={duplicate_entries}'
        )


def upgrade() -> None:
    bind = op.get_bind()
    _assert_credit_preflight(bind)

    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('auth_version', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column(
            'password_reset_required',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ))

    # Local 021 historically created admin/admin123. Existing instances must
    # fail closed until an operator chooses a replacement; custom passwords are
    # left untouched.
    legacy_admin = bind.execute(sa.text(
        "SELECT id, password_hash FROM users WHERE username = 'admin'"
    )).fetchone()
    if legacy_admin and check_password_hash(legacy_admin.password_hash, 'admin123'):
        bind.execute(
            sa.text('UPDATE users SET password_reset_required = :required WHERE id = :user_id'),
            {'required': True, 'user_id': legacy_admin.id},
        )

    with op.batch_alter_table('credit_accounts') as batch_op:
        batch_op.create_check_constraint('ck_credit_accounts_balance_nonnegative', 'balance >= 0')
        batch_op.create_check_constraint('ck_credit_accounts_reserved_nonnegative', 'reserved_balance >= 0')
        batch_op.create_check_constraint('ck_credit_accounts_reserved_within_balance', 'reserved_balance <= balance')

    with op.batch_alter_table('credit_ledger') as batch_op:
        batch_op.add_column(sa.Column('settled_at', sa.DateTime(), nullable=True))
        batch_op.create_unique_constraint(
            'uq_credit_ledger_task_entry_type',
            ['task_id', 'entry_type'],
        )

    op.create_table(
        'file_artifacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('extract_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('reference_file_id', sa.String(length=36), nullable=True),
        sa.Column('kind', sa.String(length=40), nullable=False, server_default='mineru_extract'),
        sa.Column('root_relative_path', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reference_file_id'], ['reference_files.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('extract_id', name='uq_file_artifacts_extract_id'),
    )
    op.create_index('ix_file_artifacts_user_id', 'file_artifacts', ['user_id'])
    op.create_index('ix_file_artifacts_project_id', 'file_artifacts', ['project_id'])
    op.create_index('ix_file_artifacts_reference_file_id', 'file_artifacts', ['reference_file_id'])


def downgrade() -> None:
    op.drop_index('ix_file_artifacts_reference_file_id', table_name='file_artifacts')
    op.drop_index('ix_file_artifacts_project_id', table_name='file_artifacts')
    op.drop_index('ix_file_artifacts_user_id', table_name='file_artifacts')
    op.drop_table('file_artifacts')
    with op.batch_alter_table('credit_ledger') as batch_op:
        batch_op.drop_constraint('uq_credit_ledger_task_entry_type', type_='unique')
        batch_op.drop_column('settled_at')
    with op.batch_alter_table('credit_accounts') as batch_op:
        batch_op.drop_constraint('ck_credit_accounts_reserved_within_balance', type_='check')
        batch_op.drop_constraint('ck_credit_accounts_reserved_nonnegative', type_='check')
        batch_op.drop_constraint('ck_credit_accounts_balance_nonnegative', type_='check')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('password_reset_required')
        batch_op.drop_column('auth_version')
