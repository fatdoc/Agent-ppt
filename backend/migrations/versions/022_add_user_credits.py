"""add user credits

Revision ID: 022_user_credits
Revises: 021_user_accounts
Create Date: 2026-06-24 00:00:00.000000

"""
import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text


revision = '022_user_credits'
down_revision = '021_user_accounts'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists('credit_accounts'):
        op.create_table(
            'credit_accounts',
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), primary_key=True),
            sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('reserved_balance', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('lifetime_credited', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('lifetime_spent', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )

    if not _table_exists('credit_ledger'):
        op.create_table(
            'credit_ledger',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('task_id', sa.String(length=36), sa.ForeignKey('tasks.id'), nullable=True),
            sa.Column('project_id', sa.String(length=36), sa.ForeignKey('projects.id'), nullable=True),
            sa.Column('entry_type', sa.String(length=30), nullable=False),
            sa.Column('operation', sa.String(length=80), nullable=False),
            sa.Column('amount', sa.Integer(), nullable=False),
            sa.Column('balance_after', sa.Integer(), nullable=False),
            sa.Column('reserved_after', sa.Integer(), nullable=False),
            sa.Column('metadata_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        )
        op.create_index('ix_credit_ledger_user_id', 'credit_ledger', ['user_id'])
        op.create_index('ix_credit_ledger_task_id', 'credit_ledger', ['task_id'])
        op.create_index('ix_credit_ledger_project_id', 'credit_ledger', ['project_id'])
        op.create_index('ix_credit_ledger_entry_type', 'credit_ledger', ['entry_type'])
        op.create_index('ix_credit_ledger_operation', 'credit_ledger', ['operation'])
        op.create_index('ix_credit_ledger_created_at', 'credit_ledger', ['created_at'])

    initial_balance = int(os.getenv('CREDIT_INITIAL_BALANCE', '3000'))
    if initial_balance > 0 and _table_exists('users'):
        users = bind.execute(text("SELECT id FROM users")).fetchall()
        for row in users:
            user_id = row[0]
            exists = bind.execute(
                text("SELECT 1 FROM credit_accounts WHERE user_id = :user_id"),
                {'user_id': user_id},
            ).fetchone()
            if not exists:
                bind.execute(
                    text(
                        "INSERT INTO credit_accounts "
                        "(user_id, balance, reserved_balance, lifetime_credited, lifetime_spent) "
                        "VALUES (:user_id, :balance, 0, :balance, 0)"
                    ),
                    {'user_id': user_id, 'balance': initial_balance},
                )


def downgrade() -> None:
    if _table_exists('credit_ledger'):
        op.drop_index('ix_credit_ledger_created_at', table_name='credit_ledger')
        op.drop_index('ix_credit_ledger_operation', table_name='credit_ledger')
        op.drop_index('ix_credit_ledger_entry_type', table_name='credit_ledger')
        op.drop_index('ix_credit_ledger_project_id', table_name='credit_ledger')
        op.drop_index('ix_credit_ledger_task_id', table_name='credit_ledger')
        op.drop_index('ix_credit_ledger_user_id', table_name='credit_ledger')
        op.drop_table('credit_ledger')
    if _table_exists('credit_accounts'):
        op.drop_table('credit_accounts')
