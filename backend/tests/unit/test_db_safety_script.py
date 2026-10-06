import importlib.util
import gzip
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[3] / 'scripts' / 'db_safety.py'
SPEC = importlib.util.spec_from_file_location('db_safety_script', SCRIPT_PATH)
db_safety = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(db_safety)


def _create_database(path: Path, *, ownerless: bool = False):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            'CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);'
            "INSERT INTO alembic_version VALUES ('027_public_ppt_api');"
            'CREATE TABLE users (id TEXT PRIMARY KEY);'
            'CREATE TABLE projects ('
            ' id TEXT PRIMARY KEY, user_id TEXT NULL REFERENCES users(id)'
            ');'
        )
        if ownerless:
            connection.execute("INSERT INTO projects (id, user_id) VALUES ('p1', NULL)")
        else:
            connection.execute("INSERT INTO users (id) VALUES ('u1')")
            connection.execute("INSERT INTO projects (id, user_id) VALUES ('p1', 'u1')")


def test_audit_reports_clean_database(tmp_path):
    database = tmp_path / 'clean.db'
    _create_database(database)

    summary, blocked = db_safety.audit_database(database)

    assert blocked is False
    assert summary['integrity_check'] == ['ok']
    assert summary['foreign_key_violation_count'] == 0
    assert summary['ownerless_rows'] == {}


def test_audit_blocks_ownerless_rows(tmp_path):
    database = tmp_path / 'ownerless.db'
    _create_database(database, ownerless=True)

    summary, blocked = db_safety.audit_database(database)

    assert blocked is True
    assert summary['ownerless_rows'] == {'projects': 1}


def test_backup_is_consistent_and_refuses_overwrite(tmp_path):
    source = tmp_path / 'source.db'
    backup = tmp_path / 'backup.db'
    _create_database(source)

    manifest = db_safety.backup_database(source, backup, None)

    assert backup.is_file()
    assert backup.with_suffix('.db.manifest.json').is_file()
    assert manifest['audit']['integrity_check'] == ['ok']

    try:
        db_safety.backup_database(source, backup, None)
    except FileExistsError:
        pass
    else:
        raise AssertionError('Expected an existing backup to be protected')


def _create_legacy_reference_database(path: Path, *, task_status: str = 'COMPLETED'):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            'CREATE TABLE users (id TEXT PRIMARY KEY);'
            'CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT NULL REFERENCES users(id));'
            'CREATE TABLE tasks ('
            ' id TEXT PRIMARY KEY, user_id TEXT NULL REFERENCES users(id),'
            ' project_id TEXT NULL REFERENCES projects(id), legacy_project_id TEXT NULL, status TEXT NOT NULL'
            ');'
            'CREATE TABLE credit_accounts ('
            ' user_id TEXT PRIMARY KEY, balance INTEGER NOT NULL, reserved_balance INTEGER NOT NULL,'
            ' lifetime_credited INTEGER NOT NULL, lifetime_spent INTEGER NOT NULL'
            ');'
            'CREATE TABLE credit_ledger ('
            ' id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), entry_type TEXT NOT NULL,'
            ' operation TEXT NOT NULL, amount INTEGER NOT NULL, balance_after INTEGER NOT NULL,'
            ' reserved_after INTEGER NOT NULL, project_id TEXT NULL REFERENCES projects(id),'
            ' legacy_project_id TEXT NULL, task_id TEXT NULL REFERENCES tasks(id), legacy_task_id TEXT NULL'
            ');'
            'CREATE TABLE agent_runs ('
            ' id TEXT PRIMARY KEY, project_id TEXT NULL REFERENCES projects(id),'
            ' legacy_project_id TEXT NULL, user_id TEXT NULL REFERENCES users(id)'
            ');'
            "INSERT INTO users VALUES ('u1');"
            "INSERT INTO projects VALUES ('p1', NULL);"
            f"INSERT INTO tasks VALUES ('t1', NULL, 'missing-project', NULL, '{task_status}');"
            "INSERT INTO credit_accounts VALUES ('u1', 100, 10, 150, 50);"
            "INSERT INTO credit_ledger VALUES "
            "('l1', 'u1', 'debit', 'generation', 5, 95, 10, 'missing-project', NULL, 'missing-task', NULL);"
            "INSERT INTO agent_runs VALUES ('r1', 'missing-project', NULL, 'missing-user');"
        )


def test_repair_plan_archives_rows_and_apply_preserves_legacy_references(tmp_path):
    database = tmp_path / 'legacy.db'
    archive = tmp_path / 'repair-plan.json.gz'
    _create_legacy_reference_database(database)

    plan = db_safety.create_repair_plan(
        database,
        archive,
        {'projects:p1': 'u1', 'tasks:t1': 'u1'},
    )

    assert plan['blockers'] == []
    assert plan['plan_hash']
    assert all(action['row_fingerprint'] for action in plan['actions'])
    with gzip.open(archive, 'rt', encoding='utf-8') as handle:
        archived = json.load(handle)
    assert archived['plan_hash'] == plan['plan_hash']
    assert {action['pk']['id'] for action in archived['actions']} == {'p1', 't1', 'l1', 'r1'}

    result = db_safety.apply_repair_plan(database, archive, plan['plan_hash'])

    assert result['actions_applied'] == 4
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT user_id FROM projects WHERE id="p1"').fetchone() == ('u1',)
        assert connection.execute(
            'SELECT user_id,project_id,legacy_project_id FROM tasks WHERE id="t1"'
        ).fetchone() == ('u1', None, 'missing-project')
        assert connection.execute(
            'SELECT project_id,legacy_project_id,task_id,legacy_task_id FROM credit_ledger WHERE id="l1"'
        ).fetchone() == (None, 'missing-project', None, 'missing-task')
        assert connection.execute(
            'SELECT project_id,legacy_project_id,user_id FROM agent_runs WHERE id="r1"'
        ).fetchone() == (None, 'missing-project', None)
        assert connection.execute(
            'SELECT balance,reserved_balance,lifetime_credited,lifetime_spent FROM credit_accounts'
        ).fetchone() == (100, 10, 150, 50)


def test_repair_apply_refuses_database_drift_without_partial_writes(tmp_path):
    database = tmp_path / 'drift.db'
    archive = tmp_path / 'repair-plan.json.gz'
    _create_legacy_reference_database(database)
    plan = db_safety.create_repair_plan(database, archive, {'projects:p1': 'u1', 'tasks:t1': 'u1'})
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE credit_accounts SET balance=101 WHERE user_id='u1'")

    with pytest.raises(db_safety.RepairBlocked, match='database drift'):
        db_safety.apply_repair_plan(database, archive, plan['plan_hash'])

    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT user_id FROM projects WHERE id="p1"').fetchone() == (None,)
        assert connection.execute('SELECT balance FROM credit_accounts WHERE user_id="u1"').fetchone() == (101,)


def test_repair_plan_blocks_non_terminal_orphan_task(tmp_path):
    database = tmp_path / 'running.db'
    archive = tmp_path / 'repair-plan.json.gz'
    _create_legacy_reference_database(database, task_status='RUNNING')

    plan = db_safety.create_repair_plan(database, archive, {'projects:p1': 'u1', 'tasks:t1': 'u1'})

    assert any('non-terminal task' in blocker for blocker in plan['blockers'])
    with pytest.raises(db_safety.RepairBlocked, match='non-terminal task'):
        db_safety.apply_repair_plan(database, archive, plan['plan_hash'])


def _create_agent_graph_database(path: Path, *, job_status: str = 'COMPLETED'):
    with sqlite3.connect(path) as connection:
        connection.executescript(
            'CREATE TABLE users (id TEXT PRIMARY KEY);'
            'CREATE TABLE projects (id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id));'
            'CREATE TABLE deck_versions ('
            ' id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id)'
            ');'
            'CREATE TABLE slide_versions ('
            ' id TEXT PRIMARY KEY, deck_version_id TEXT NOT NULL REFERENCES deck_versions(id)'
            ');'
            'CREATE TABLE generation_jobs ('
            ' id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),'
            ' slide_version_id TEXT REFERENCES slide_versions(id), status TEXT NOT NULL'
            ');'
            "INSERT INTO deck_versions VALUES ('deck-1', 'missing-project');"
            "INSERT INTO slide_versions VALUES ('slide-1', 'deck-1');"
            f"INSERT INTO generation_jobs VALUES ('job-1', 'missing-project', 'slide-1', '{job_status}');"
        )


def test_repair_archives_and_deletes_unrecoverable_agent_graph(tmp_path):
    database = tmp_path / 'agent.db'
    archive = tmp_path / 'agent-plan.json.gz'
    _create_agent_graph_database(database)

    plan = db_safety.create_repair_plan(database, archive)

    assert plan['blockers'] == []
    assert {(item['table'], item['pk']['id']) for item in plan['actions']} == {
        ('deck_versions', 'deck-1'),
        ('slide_versions', 'slide-1'),
        ('generation_jobs', 'job-1'),
    }
    assert all(item['row'] for item in plan['actions'])
    db_safety.apply_repair_plan(database, archive, plan['plan_hash'])
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT COUNT(*) FROM deck_versions').fetchone() == (0,)
        assert connection.execute('SELECT COUNT(*) FROM slide_versions').fetchone() == (0,)
        assert connection.execute('SELECT COUNT(*) FROM generation_jobs').fetchone() == (0,)


def test_repair_blocks_non_terminal_generation_job(tmp_path):
    database = tmp_path / 'agent-running.db'
    archive = tmp_path / 'agent-plan.json.gz'
    _create_agent_graph_database(database, job_status='RUNNING')

    plan = db_safety.create_repair_plan(database, archive)

    assert any('non-terminal GenerationJob' in blocker for blocker in plan['blockers'])
    with pytest.raises(db_safety.RepairBlocked, match='non-terminal GenerationJob'):
        db_safety.apply_repair_plan(database, archive, plan['plan_hash'])


def test_repair_rejects_tampered_plan_and_duplicate_apply(tmp_path):
    database = tmp_path / 'legacy.db'
    archive = tmp_path / 'repair-plan.json.gz'
    _create_legacy_reference_database(database)
    plan = db_safety.create_repair_plan(database, archive, {'projects:p1': 'u1', 'tasks:t1': 'u1'})

    with gzip.open(archive, 'rt', encoding='utf-8') as handle:
        tampered = json.load(handle)
    tampered['actions'][0]['reasons'].append('tampered')
    tampered_archive = tmp_path / 'tampered.json.gz'
    with gzip.open(tampered_archive, 'wt', encoding='utf-8') as handle:
        json.dump(tampered, handle)
    with pytest.raises(db_safety.RepairBlocked, match='invalid plan hash'):
        db_safety.apply_repair_plan(database, tampered_archive, plan['plan_hash'])

    db_safety.apply_repair_plan(database, archive, plan['plan_hash'])
    with pytest.raises(db_safety.RepairBlocked, match='database drift'):
        db_safety.apply_repair_plan(database, archive, plan['plan_hash'])


def test_restore_quarantines_current_database_and_sidecars(tmp_path, monkeypatch):
    source = tmp_path / 'source.db'
    backup = tmp_path / 'backup.db'
    database = tmp_path / 'live.db'
    quarantine = tmp_path / 'quarantine'
    _create_database(source)
    _create_database(database)
    with sqlite3.connect(source) as connection:
        connection.executescript(
            'CREATE TABLE child (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id));'
            "INSERT INTO child VALUES ('c1', 'known-missing-project');"
            "UPDATE projects SET id='from-backup' WHERE id='p1';"
        )
    connection.close()
    manifest = db_safety.backup_database(source, backup, None)
    assert manifest['audit']['foreign_key_violation_count'] == 1
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE projects SET id='from-live' WHERE id='p1'")
    connection.close()
    Path(str(database) + '-wal').write_bytes(b'closed-wal')
    Path(str(database) + '-shm').write_bytes(b'closed-shm')
    # Handle detection is tested independently; pytest/plugins can themselves
    # retain a descriptor to a just-closed SQLite file on macOS.
    monkeypatch.setattr(db_safety, '_closed', lambda _database: None)

    result = db_safety.restore_database(backup, database, quarantine)

    assert result['audit']['integrity_check'] == ['ok']
    with sqlite3.connect(database) as connection:
        assert connection.execute('SELECT id FROM projects').fetchone() == ('from-backup',)
        assert connection.execute('PRAGMA foreign_key_check').fetchall()
    assert (quarantine / 'live.db').is_file()
    assert (quarantine / 'live.db-wal').read_bytes() == b'closed-wal'
    assert (quarantine / 'live.db-shm').read_bytes() == b'closed-shm'


def test_restore_rejects_manifest_mismatch_and_open_handle(tmp_path, monkeypatch):
    source = tmp_path / 'source.db'
    backup = tmp_path / 'backup.db'
    database = tmp_path / 'live.db'
    _create_database(source)
    _create_database(database)
    db_safety.backup_database(source, backup, None)
    with backup.open('ab') as handle:
        handle.write(b'tampered')

    with pytest.raises(db_safety.RepairBlocked, match='manifest SHA-256 mismatch'):
        db_safety.restore_database(backup, database, tmp_path / 'quarantine')

    monkeypatch.setattr(db_safety.shutil, 'which', lambda _name: '/usr/sbin/lsof')
    monkeypatch.setattr(
        db_safety.subprocess,
        'run',
        lambda *args, **kwargs: SimpleNamespace(stdout='123\n'),
    )
    with pytest.raises(db_safety.RepairBlocked, match='open handle'):
        db_safety._closed(database)
