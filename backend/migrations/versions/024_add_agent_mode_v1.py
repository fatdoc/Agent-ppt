"""add agent mode v1 planning tables

Revision ID: 024_agent_mode_v1
Revises: 023_visual_strategy
Create Date: 2026-06-27 02:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '024_agent_mode_v1'
down_revision = '023_visual_strategy'
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _table_exists('deck_versions'):
        op.create_table(
            'deck_versions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
            sa.Column('deck_plan', sa.Text(), nullable=True),
            sa.Column('qa_result', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_deck_versions_project_id', 'deck_versions', ['project_id'])

    if not _table_exists('slide_versions'):
        op.create_table(
            'slide_versions',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('deck_version_id', sa.String(length=36), nullable=False),
            sa.Column('page_id', sa.String(length=36), nullable=False),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('order_index', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending_confirmation'),
            sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('slide_plan', sa.Text(), nullable=False),
            sa.Column('qa_result', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['deck_version_id'], ['deck_versions.id']),
            sa.ForeignKeyConstraint(['page_id'], ['pages.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_slide_versions_deck_version_id', 'slide_versions', ['deck_version_id'])
        op.create_index('ix_slide_versions_page_id', 'slide_versions', ['page_id'])

    if not _table_exists('deck_visual_systems'):
        op.create_table(
            'deck_visual_systems',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('deck_version_id', sa.String(length=36), nullable=False),
            sa.Column('strategy_id', sa.String(length=64), nullable=False, server_default='native'),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('system_json', sa.Text(), nullable=False),
            sa.Column('qa_result', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['deck_version_id'], ['deck_versions.id']),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_deck_visual_systems_project_id', 'deck_visual_systems', ['project_id'])
        op.create_index('ix_deck_visual_systems_deck_version_id', 'deck_visual_systems', ['deck_version_id'])

    if not _table_exists('page_visual_plans'):
        op.create_table(
            'page_visual_plans',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('page_id', sa.String(length=36), nullable=False),
            sa.Column('slide_version_id', sa.String(length=36), nullable=False),
            sa.Column('deck_visual_system_id', sa.String(length=36), nullable=False),
            sa.Column('strategy_id', sa.String(length=64), nullable=False, server_default='native'),
            sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('plan_json', sa.Text(), nullable=False),
            sa.Column('qa_result', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending_confirmation'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['deck_visual_system_id'], ['deck_visual_systems.id']),
            sa.ForeignKeyConstraint(['page_id'], ['pages.id']),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.ForeignKeyConstraint(['slide_version_id'], ['slide_versions.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_page_visual_plans_project_id', 'page_visual_plans', ['project_id'])
        op.create_index('ix_page_visual_plans_page_id', 'page_visual_plans', ['page_id'])
        op.create_index('ix_page_visual_plans_slide_version_id', 'page_visual_plans', ['slide_version_id'])

    if not _table_exists('agent_runs'):
        op.create_table(
            'agent_runs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=True),
            sa.Column('project_id', sa.String(length=36), nullable=True),
            sa.Column('run_type', sa.String(length=64), nullable=False, server_default='agent_mode_v1'),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
            sa.Column('input_json', sa.Text(), nullable=True),
            sa.Column('output_json', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_agent_runs_project_id', 'agent_runs', ['project_id'])
        op.create_index('ix_agent_runs_user_id', 'agent_runs', ['user_id'])

    if not _table_exists('agent_steps'):
        op.create_table(
            'agent_steps',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('agent_run_id', sa.String(length=36), nullable=False),
            sa.Column('step_name', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
            sa.Column('input_json', sa.Text(), nullable=True),
            sa.Column('output_json', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_agent_steps_agent_run_id', 'agent_steps', ['agent_run_id'])

    if not _table_exists('agent_tool_calls'):
        op.create_table(
            'agent_tool_calls',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('agent_run_id', sa.String(length=36), nullable=False),
            sa.Column('tool_name', sa.String(length=96), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='running'),
            sa.Column('input_json', sa.Text(), nullable=True),
            sa.Column('output_json', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_agent_tool_calls_agent_run_id', 'agent_tool_calls', ['agent_run_id'])

    if not _table_exists('generation_jobs'):
        op.create_table(
            'generation_jobs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('project_id', sa.String(length=36), nullable=False),
            sa.Column('page_id', sa.String(length=36), nullable=False),
            sa.Column('slide_version_id', sa.String(length=36), nullable=False),
            sa.Column('visual_plan_version_id', sa.String(length=36), nullable=False),
            sa.Column('task_id', sa.String(length=36), nullable=True),
            sa.Column('job_type', sa.String(length=32), nullable=False, server_default='style_preview'),
            sa.Column('idempotency_key', sa.String(length=128), nullable=False),
            sa.Column('input_hash', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['page_id'], ['pages.id']),
            sa.ForeignKeyConstraint(['project_id'], ['projects.id']),
            sa.ForeignKeyConstraint(['slide_version_id'], ['slide_versions.id']),
            sa.ForeignKeyConstraint(['task_id'], ['tasks.id']),
            sa.ForeignKeyConstraint(['visual_plan_version_id'], ['page_visual_plans.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_generation_jobs_project_id', 'generation_jobs', ['project_id'])
        op.create_index('ix_generation_jobs_page_id', 'generation_jobs', ['page_id'])
        op.create_index('ix_generation_jobs_slide_version_id', 'generation_jobs', ['slide_version_id'])
        op.create_index('ix_generation_jobs_visual_plan_version_id', 'generation_jobs', ['visual_plan_version_id'])
        op.create_index('ix_generation_jobs_task_id', 'generation_jobs', ['task_id'])
        op.create_index('ix_generation_jobs_idempotency_key', 'generation_jobs', ['idempotency_key'])


def downgrade() -> None:
    for table in (
        'generation_jobs',
        'agent_tool_calls',
        'agent_steps',
        'agent_runs',
        'page_visual_plans',
        'deck_visual_systems',
        'slide_versions',
        'deck_versions',
    ):
        if _table_exists(table):
            op.drop_table(table)
