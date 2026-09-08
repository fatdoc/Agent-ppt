from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from models import AgentRun, CreditLedger, Task


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / 'alembic.ini'))
    config.set_main_option('script_location', str(BACKEND_DIR / 'migrations'))
    config.set_main_option('sqlalchemy.url', database_url)
    return config


def _upgrade(monkeypatch, database, target='head'):
    database_url = f'sqlite:///{database}'
    monkeypatch.setenv('DATABASE_URL', database_url)
    command.upgrade(_config(database_url), target)
    return database_url


def test_combined_lineage_has_one_head(monkeypatch, tmp_path):
    database_url = f'sqlite:///{tmp_path / "graph.db"}'
    monkeypatch.setenv('DATABASE_URL', database_url)
    heads = ScriptDirectory.from_config(_config(database_url)).get_heads()
    assert heads == ['030_batch01_safety_expand']


def test_legacy_reference_fields_are_not_exposed_in_api_payloads():
    task = Task(legacy_project_id='archived-project')
    ledger = CreditLedger(
        legacy_project_id='archived-project',
        legacy_task_id='archived-task',
    )
    run = AgentRun(legacy_project_id='archived-project')

    assert 'legacy_project_id' not in task.to_dict()
    assert 'legacy_project_id' not in ledger.to_dict()
    assert 'legacy_task_id' not in ledger.to_dict()
    assert 'legacy_project_id' not in run.to_dict()


def test_empty_database_upgrades_to_combined_head(monkeypatch, tmp_path):
    database = tmp_path / 'empty.db'
    database_url = _upgrade(monkeypatch, database)
    engine = create_engine(database_url)
    inspector = inspect(engine)

    with engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '030_batch01_safety_expand'
        assert connection.execute(text('PRAGMA foreign_key_check')).fetchall() == []
        admin = connection.execute(text(
            "SELECT password_hash, password_reset_required FROM users WHERE username = 'admin'"
        )).one()
        # Fresh installs receive an unpredictable owner credential. In
        # particular, the historical shared admin/admin123 credential is not
        # usable even when password_reset_required is false.
        assert not check_password_hash(admin.password_hash, 'admin123')
        assert not (
            check_password_hash(admin.password_hash, 'admin123')
            and not bool(admin.password_reset_required)
        )

    assert 'project_template_assets' in inspector.get_table_names()
    assert 'file_artifacts' in inspector.get_table_names()
    assert 'auth_version' in {column['name'] for column in inspector.get_columns('users')}
    assert 'settled_at' in {column['name'] for column in inspector.get_columns('credit_ledger')}
    task_columns = {column['name']: column for column in inspector.get_columns('tasks')}
    assert task_columns['project_id']['nullable'] is True
    assert 'legacy_project_id' in task_columns
    assert {'legacy_project_id', 'legacy_task_id'} <= {
        column['name'] for column in inspector.get_columns('credit_ledger')
    }
    assert 'legacy_project_id' in {
        column['name'] for column in inspector.get_columns('agent_runs')
    }


def test_local_027_and_upstream_784_each_converge_to_head(monkeypatch, tmp_path):
    for starting_revision in ('027_public_ppt_api', '78475bbce762'):
        database = tmp_path / f'{starting_revision}.db'
        database_url = _upgrade(monkeypatch, database, starting_revision)
        command.upgrade(_config(database_url), 'head')
        engine = create_engine(database_url)
        with engine.connect() as connection:
            assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '030_batch01_safety_expand'
            assert connection.execute(text('PRAGMA foreign_key_check')).fetchall() == []


def test_027a_is_expand_only_and_028_fails_closed_on_orphans(monkeypatch, tmp_path):
    database = tmp_path / 'orphaned-local-027.db'
    database_url = _upgrade(monkeypatch, database, '027_public_ppt_api')
    engine = create_engine(database_url)
    with engine.connect() as connection:
        # The application registers a class-level Engine listener that enables
        # SQLite FK enforcement. This fixture intentionally represents a
        # historical database created while enforcement was off, so disable it
        # on this connection before any DML and finish PRAGMA's autobegin first.
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        connection.commit()
        assert connection.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 0
        connection.commit()
        with connection.begin():
            admin_id = connection.execute(text(
                "SELECT id FROM users WHERE username = 'admin'"
            )).scalar_one()
            connection.execute(text(
                "INSERT INTO tasks "
                "(id, user_id, project_id, task_type, status, created_at) "
                "VALUES ('legacy-task', :user_id, 'missing-project', "
                "'GENERATE_IMAGES', 'FAILED', CURRENT_TIMESTAMP)"
            ), {'user_id': admin_id})
            connection.execute(text(
                "INSERT INTO credit_ledger "
                "(id, user_id, task_id, project_id, entry_type, operation, amount, "
                "balance_after, reserved_after, created_at) VALUES "
                "('legacy-ledger', :user_id, 'missing-task', 'missing-project', "
                "'grant', 'legacy', 0, 0, 0, CURRENT_TIMESTAMP)"
            ), {'user_id': admin_id})
            connection.execute(text(
                "INSERT INTO agent_runs "
                "(id, user_id, project_id, run_type, status, created_at) "
                "VALUES ('legacy-run', :user_id, 'missing-project', "
                "'agent_mode_v1', 'failed', CURRENT_TIMESTAMP)"
            ), {'user_id': admin_id})

    command.upgrade(_config(database_url), '027a_legacy_references')

    with engine.connect() as connection:
        task = connection.execute(text(
            "SELECT project_id, legacy_project_id FROM tasks WHERE id = 'legacy-task'"
        )).one()
        assert task.project_id == 'missing-project'
        assert task.legacy_project_id is None
        ledger = connection.execute(text(
            "SELECT project_id, task_id, legacy_project_id, legacy_task_id "
            "FROM credit_ledger WHERE id = 'legacy-ledger'"
        )).one()
        assert ledger.project_id == 'missing-project'
        assert ledger.task_id == 'missing-task'
        assert ledger.legacy_project_id is None
        assert ledger.legacy_task_id is None
        run = connection.execute(text(
            "SELECT project_id, legacy_project_id FROM agent_runs WHERE id = 'legacy-run'"
        )).one()
        assert run.project_id == 'missing-project'
        assert run.legacy_project_id is None

    try:
        command.upgrade(_config(database_url), '028_local_integrity')
    except RuntimeError as exc:
        assert 'Foreign-key preflight failed' in str(exc)
    else:
        raise AssertionError('028 must refuse orphan repair that was not applied explicitly')


def test_027a_clean_downgrade_removes_only_expand_schema(monkeypatch, tmp_path):
    database = tmp_path / 'clean-027a-downgrade.db'
    database_url = _upgrade(monkeypatch, database, '027a_legacy_references')

    command.downgrade(_config(database_url), '027_public_ppt_api')

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert 'legacy_project_id' not in {
        column['name'] for column in inspector.get_columns('tasks')
    }
    project_column = next(
        column for column in inspector.get_columns('tasks') if column['name'] == 'project_id'
    )
    assert project_column['nullable'] is False


def test_027a_downgrade_refuses_to_discard_preserved_reference(monkeypatch, tmp_path):
    database = tmp_path / 'preserved-027a-downgrade.db'
    database_url = _upgrade(monkeypatch, database, '027a_legacy_references')
    engine = create_engine(database_url)
    with engine.begin() as connection:
        admin_id = connection.execute(text(
            "SELECT id FROM users WHERE username = 'admin'"
        )).scalar_one()
        connection.execute(text(
            "INSERT INTO projects "
            "(id, user_id, creation_type, image_aspect_ratio, status, created_at, updated_at) "
            "VALUES ('current-project', :user_id, 'idea', '16:9', 'DRAFT', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {'user_id': admin_id})
        connection.execute(text(
            "INSERT INTO tasks "
            "(id, user_id, project_id, legacy_project_id, task_type, status, created_at) "
            "VALUES ('preserved-task', :user_id, 'current-project', 'archived-project', "
            "'GENERATE_IMAGES', 'FAILED', CURRENT_TIMESTAMP)"
        ), {'user_id': admin_id})

    try:
        command.downgrade(_config(database_url), '027_public_ppt_api')
    except RuntimeError as exc:
        assert 'preserved legacy reference' in str(exc)
    else:
        raise AssertionError('Downgrade must not discard preserved legacy references')


def test_combined_head_matches_orm_metadata(monkeypatch, tmp_path):
    database = tmp_path / 'alembic-check.db'
    database_url = _upgrade(monkeypatch, database)
    command.check(_config(database_url))


def test_legacy_admin_default_password_is_marked_for_reset(monkeypatch, tmp_path):
    database = tmp_path / 'legacy-admin.db'
    database_url = _upgrade(monkeypatch, database, '029_merge_local_upstream')
    engine = create_engine(database_url)
    legacy_hash = generate_password_hash('admin123')
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET password_hash = :password_hash WHERE username = 'admin'"),
            {'password_hash': legacy_hash},
        )

    command.upgrade(_config(database_url), 'head')

    with engine.connect() as connection:
        admin = connection.execute(text(
            "SELECT password_hash, password_reset_required FROM users WHERE username = 'admin'"
        )).one()
        assert check_password_hash(admin.password_hash, 'admin123')
        assert bool(admin.password_reset_required) is True
        assert not (
            check_password_hash(admin.password_hash, 'admin123')
            and not bool(admin.password_reset_required)
        )


def test_custom_admin_password_is_not_forced_into_reset(monkeypatch, tmp_path):
    database = tmp_path / 'custom-admin.db'
    database_url = _upgrade(monkeypatch, database, '029_merge_local_upstream')
    engine = create_engine(database_url)
    custom_hash = generate_password_hash('operator-chosen-password')
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE users SET password_hash = :password_hash WHERE username = 'admin'"),
            {'password_hash': custom_hash},
        )

    command.upgrade(_config(database_url), 'head')

    with engine.connect() as connection:
        admin = connection.execute(text(
            "SELECT password_hash, password_reset_required FROM users WHERE username = 'admin'"
        )).one()
        assert check_password_hash(admin.password_hash, 'operator-chosen-password')
        assert bool(admin.password_reset_required) is False
