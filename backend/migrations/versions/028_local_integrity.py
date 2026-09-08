"""enforce Local ownership metadata integrity before lineage merge

Revision ID: 028_local_integrity
Revises: 027a_legacy_references
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = '028_local_integrity'
down_revision = '027a_legacy_references'
branch_labels = None
depends_on = None


OWNER_TABLES = (
    'projects',
    'settings',
    'user_templates',
    'user_style_templates',
    'reference_files',
    'materials',
    'tasks',
)


def _assert_preflight_clean(bind) -> None:
    if bind.dialect.name == 'sqlite':
        violations = bind.execute(sa.text('PRAGMA foreign_key_check')).fetchall()
        if violations:
            sample = ', '.join(f'{row[0]}:{row[1]}' for row in violations[:5])
            raise RuntimeError(
                f'Foreign-key preflight failed with {len(violations)} violation(s); '
                f'run scripts/db_safety.py audit before upgrading (sample: {sample})'
            )

    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    ownerless = {}
    for table_name in OWNER_TABLES:
        if table_name not in existing_tables:
            continue
        columns = {column['name'] for column in inspector.get_columns(table_name)}
        if 'user_id' not in columns:
            continue
        count = bind.execute(sa.text(
            f'SELECT COUNT(*) FROM {table_name} WHERE user_id IS NULL'
        )).scalar_one()
        if count:
            ownerless[table_name] = int(count)
    if ownerless:
        details = ', '.join(f'{name}={count}' for name, count in sorted(ownerless.items()))
        raise RuntimeError(
            f'Ownership preflight failed ({details}); assign or archive these rows before upgrading'
        )


def _has_user_fk(inspector, table_name: str) -> bool:
    return any(
        fk.get('referred_table') == 'users' and fk.get('constrained_columns') == ['user_id']
        for fk in inspector.get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    _assert_preflight_clean(bind)
    inspector = inspect(bind)

    for table_name in OWNER_TABLES:
        if table_name not in inspector.get_table_names() or _has_user_fk(inspector, table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_foreign_key(
                f'fk_{table_name}_user_id_users',
                'users',
                ['user_id'],
                ['id'],
                ondelete='CASCADE',
            )

    settings_indexes = {item['name']: item for item in inspect(bind).get_indexes('settings')}
    current = settings_indexes.get('ix_settings_user_id')
    if current and not current.get('unique'):
        with op.batch_alter_table('settings') as batch_op:
            batch_op.drop_index('ix_settings_user_id')
            batch_op.create_index('ix_settings_user_id', ['user_id'], unique=True)

    page_visual_indexes = {item['name'] for item in inspect(bind).get_indexes('page_visual_plans')}
    if 'ix_page_visual_plans_deck_visual_system_id' not in page_visual_indexes:
        op.create_index(
            'ix_page_visual_plans_deck_visual_system_id',
            'page_visual_plans',
            ['deck_visual_system_id'],
        )

    redundant_indexes = (
        ('users', 'ix_users_username'),
        ('users', 'ix_users_email'),
        ('api_keys', 'ix_api_keys_key_prefix'),
        ('public_ppt_generations', 'ix_public_ppt_generations_project_id'),
    )
    for table_name, index_name in redundant_indexes:
        indexes = {item['name'] for item in inspect(bind).get_indexes(table_name)}
        if index_name in indexes:
            op.drop_index(index_name, table_name=table_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    for table_name, index_name, columns in (
        ('users', 'ix_users_username', ['username']),
        ('users', 'ix_users_email', ['email']),
        ('api_keys', 'ix_api_keys_key_prefix', ['key_prefix']),
        ('public_ppt_generations', 'ix_public_ppt_generations_project_id', ['project_id']),
    ):
        indexes = {item['name'] for item in inspect(bind).get_indexes(table_name)}
        if index_name not in indexes:
            op.create_index(index_name, table_name, columns)
    page_visual_indexes = {item['name'] for item in inspector.get_indexes('page_visual_plans')}
    if 'ix_page_visual_plans_deck_visual_system_id' in page_visual_indexes:
        op.drop_index('ix_page_visual_plans_deck_visual_system_id', table_name='page_visual_plans')

    settings_indexes = {item['name']: item for item in inspect(bind).get_indexes('settings')}
    current = settings_indexes.get('ix_settings_user_id')
    if current and current.get('unique'):
        with op.batch_alter_table('settings') as batch_op:
            batch_op.drop_index('ix_settings_user_id')
            batch_op.create_index('ix_settings_user_id', ['user_id'], unique=False)

    for table_name in reversed(OWNER_TABLES):
        fk_name = f'fk_{table_name}_user_id_users'
        names = {fk.get('name') for fk in inspect(bind).get_foreign_keys(table_name)}
        if fk_name in names:
            with op.batch_alter_table(table_name) as batch_op:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
