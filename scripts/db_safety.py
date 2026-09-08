#!/usr/bin/env python3
"""Fail-closed SQLite audit, backup, repair-plan/apply, and restore utility."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OWNER_TABLES = ('projects', 'settings', 'user_templates', 'user_style_templates', 'reference_files', 'materials', 'tasks')
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'CANCELED'}
AGENT_TABLES = ('deck_versions', 'slide_versions', 'deck_visual_systems', 'page_visual_plans', 'generation_jobs')


class RepairBlocked(RuntimeError):
    pass


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _ro(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f'file:{path.resolve()}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only=ON')
    return connection


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )}


def _columns(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {row['name']: row for row in connection.execute(f'PRAGMA table_info({_q(table)})')}


def _pk_columns(connection: sqlite3.Connection, table: str) -> list[str]:
    columns = sorted(_columns(connection, table).values(), key=lambda row: row['pk'])
    return [row['name'] for row in columns if row['pk']] or ['rowid']


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), default=str).encode()


def _fingerprint(row: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(row)).hexdigest()


def _pk(connection: sqlite3.Connection, table: str, row: dict[str, Any]) -> dict[str, Any]:
    return {name: row[name] for name in _pk_columns(connection, table)}


def _where(pk: dict[str, Any]) -> tuple[str, list[Any]]:
    return ' AND '.join(f'{_q(key)} IS ?' for key in pk), list(pk.values())


def _rows(connection: sqlite3.Connection, table: str, where: str = '1=1', params: tuple = ()) -> list[dict]:
    return [_row(item) for item in connection.execute(f'SELECT rowid, * FROM {_q(table)} WHERE {where}', params)]


def _database_fingerprint(connection: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    for table in sorted(_tables(connection)):
        schema = connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
        digest.update(_canonical([table, schema]))
        order = ','.join(_q(name) for name in _pk_columns(connection, table))
        for row in connection.execute(f'SELECT rowid, * FROM {_q(table)} ORDER BY {order}'):
            digest.update(_canonical(_row(row)))
    return digest.hexdigest()


def _credit(connection: sqlite3.Connection, tables: set[str]) -> dict:
    result = {'invalid_accounts': 0, 'duplicate_task_entry_types': 0}
    if 'credit_accounts' in tables:
        result['invalid_accounts'] = connection.execute(
            'SELECT COUNT(*) FROM credit_accounts WHERE balance<0 OR reserved_balance<0 OR reserved_balance>balance'
        ).fetchone()[0]
        rows = [list(row) for row in connection.execute(
            'SELECT user_id,balance,reserved_balance,lifetime_credited,lifetime_spent FROM credit_accounts ORDER BY user_id'
        )]
        result['accounts_fingerprint'] = hashlib.sha256(_canonical(rows)).hexdigest()
    if 'credit_ledger' in tables:
        result['duplicate_task_entry_types'] = connection.execute(
            "SELECT COUNT(*) FROM (SELECT task_id,entry_type FROM credit_ledger WHERE task_id IS NOT NULL "
            "AND entry_type IN ('reserve','debit','release') GROUP BY task_id,entry_type HAVING COUNT(*)>1)"
        ).fetchone()[0]
        rows = [list(row) for row in connection.execute(
            'SELECT id,user_id,entry_type,operation,amount,balance_after,reserved_after FROM credit_ledger ORDER BY id'
        )]
        result['ledger_fingerprint'] = hashlib.sha256(_canonical(rows)).hexdigest()
    return result


def _snapshot(connection: sqlite3.Connection) -> dict:
    tables = _tables(connection)
    ownerless = {}
    for table in OWNER_TABLES:
        if table in tables and 'user_id' in _columns(connection, table):
            count = connection.execute(f'SELECT COUNT(*) FROM {_q(table)} WHERE user_id IS NULL').fetchone()[0]
            if count:
                ownerless[table] = count
    return {
        'integrity': [row[0] for row in connection.execute('PRAGMA integrity_check')],
        'foreign_keys': [list(row) for row in connection.execute('PRAGMA foreign_key_check')],
        'ownerless': ownerless,
        'row_counts': {table: connection.execute(f'SELECT COUNT(*) FROM {_q(table)}').fetchone()[0] for table in sorted(tables)},
        'credit': _credit(connection, tables),
    }


def audit_database(path: Path) -> tuple[dict, bool]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with _ro(path) as connection:
        state = _snapshot(connection)
        revisions = [row[0] for row in connection.execute('SELECT version_num FROM alembic_version')] if 'alembic_version' in _tables(connection) else []
    summary = {
        'database': str(path.resolve()), 'size_bytes': path.stat().st_size, 'alembic_revisions': revisions,
        'integrity_check': state['integrity'], 'foreign_key_violation_count': len(state['foreign_keys']),
        'foreign_key_violation_tables': sorted({row[0] for row in state['foreign_keys']}),
        'ownerless_rows': state['ownerless'], 'credit': state['credit'],
    }
    blocked = state['integrity'] != ['ok'] or bool(state['foreign_keys']) or bool(state['ownerless']) or any(
        state['credit'].get(key, 0) for key in ('invalid_accounts', 'duplicate_task_entry_types')
    )
    return summary, blocked


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def backup_database(source: Path, destination: Path, uploads: Path | None) -> dict:
    if not source.is_file():
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite backup: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with _ro(source) as source_connection, sqlite3.connect(destination) as target:
        source_connection.backup(target)
    audit, blocked = audit_database(destination)
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'source': str(source.resolve()),
                'database_backup': str(destination.resolve()), 'database_sha256': _sha256(destination),
                'audit': audit, 'migration_blocked': blocked, 'uploads': []}
    if uploads:
        if not uploads.is_dir():
            raise NotADirectoryError(uploads)
        for item in sorted(path for path in uploads.rglob('*') if path.is_file()):
            manifest['uploads'].append({'path': item.relative_to(uploads).as_posix(), 'size_bytes': item.stat().st_size, 'sha256': _sha256(item)})
    destination.with_suffix(destination.suffix + '.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


def parse_owner_specs(specs: list[str]) -> dict[str, str]:
    result = {}
    for spec in specs:
        if '=' not in spec:
            raise ValueError(f'Invalid owner mapping: {spec}')
        key, value = (part.strip() for part in spec.split('=', 1))
        if not key or not value:
            raise ValueError(f'Invalid owner mapping: {spec}')
        result[key] = value
    return result


def _owner(mapping: dict[str, str], table: str, pk: dict) -> str | None:
    value = next(iter(pk.values())) if len(pk) == 1 else json.dumps(pk, sort_keys=True)
    return mapping.get(f'{table}:{value}') or mapping.get(f'{table}:*') or mapping.get('*')


def _update(actions: dict, connection: sqlite3.Connection, table: str, row: dict, changes: dict, reason: str) -> None:
    pk = _pk(connection, table, row); key = (table, json.dumps(pk, sort_keys=True))
    action = actions.setdefault(key, {'action': 'update', 'table': table, 'pk': pk, 'row': row,
                                     'row_fingerprint': _fingerprint(row), 'changes': {}, 'reasons': []})
    action['changes'].update(changes); action['reasons'].append(reason)


def _delete(actions: dict, connection: sqlite3.Connection, table: str, row: dict) -> None:
    pk = _pk(connection, table, row)
    actions[(table, json.dumps(pk, sort_keys=True))] = {'action': 'delete', 'table': table, 'pk': pk, 'row': row,
        'row_fingerprint': _fingerprint(row), 'changes': {}, 'reasons': ['archive irrecoverable Agent graph']}


def _execute(connection: sqlite3.Connection, actions: list[dict]) -> None:
    for action in actions:
        clause, pk_values = _where(action['pk'])
        if action['action'] == 'update':
            names = list(action['changes']); values = [action['changes'][name] for name in names]
            connection.execute(f"UPDATE {_q(action['table'])} SET " + ','.join(f'{_q(name)}=?' for name in names) + f' WHERE {clause}', values + pk_values)
        else:
            connection.execute(f"DELETE FROM {_q(action['table'])} WHERE {clause}", pk_values)


def _hash_plan(plan: dict) -> str:
    return hashlib.sha256(_canonical({key: value for key, value in plan.items() if key != 'plan_hash'})).hexdigest()


def create_repair_plan(database: Path, output: Path, owner_mappings: dict[str, str] | None = None) -> dict:
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite repair plan: {output}')
    mappings = owner_mappings or {}; actions = {}; blockers = []
    with _ro(database) as connection:
        tables = _tables(connection); before = _snapshot(connection)
        users = {row[0] for row in connection.execute('SELECT id FROM users')} if 'users' in tables else set()
        project_owners = {row['id']: row['user_id'] for row in connection.execute('SELECT id,user_id FROM projects')} if 'projects' in tables else {}
        for table in OWNER_TABLES:
            if table not in tables or 'user_id' not in _columns(connection, table): continue
            for row in _rows(connection, table, 'user_id IS NULL OR user_id NOT IN (SELECT id FROM users)'):
                pk = _pk(connection, table, row); owner = _owner(mappings, table, pk)
                if not owner and row.get('project_id'): owner = project_owners.get(row['project_id'])
                if owner not in users: blockers.append(f'{table} {pk} requires valid owner mapping'); continue
                _update(actions, connection, table, row, {'user_id': owner}, 'confirmed ownership')
                if table == 'projects': project_owners[row['id']] = owner
        for table, column, parent, legacy, terminal_check in (
            ('tasks','project_id','projects','legacy_project_id',True),
            ('credit_ledger','project_id','projects','legacy_project_id',False),
            ('credit_ledger','task_id','tasks','legacy_task_id',False),
            ('agent_runs','project_id','projects','legacy_project_id',False),
        ):
            if table not in tables or parent not in tables or column not in _columns(connection, table): continue
            columns = _columns(connection, table)
            for row in _rows(connection, table, f'{_q(column)} IS NOT NULL AND {_q(column)} NOT IN (SELECT id FROM {_q(parent)})'):
                pk = _pk(connection, table, row)
                if terminal_check and str(row.get('status','')).upper() not in TERMINAL:
                    blockers.append(f'non-terminal task {pk} references missing project'); continue
                if legacy not in columns or columns[column]['notnull']:
                    blockers.append(f'{table} {pk} requires 027a nullable/legacy schema'); continue
                if row.get(legacy) not in (None, row[column]): blockers.append(f'{table} {pk} has conflicting {legacy}'); continue
                _update(actions, connection, table, row, {legacy: row[column], column: None}, 'preserve legacy reference then null')
        if 'agent_runs' in tables and 'users' in tables and not _columns(connection, 'agent_runs')['user_id']['notnull']:
            for row in _rows(connection, 'agent_runs', 'user_id IS NOT NULL AND user_id NOT IN (SELECT id FROM users)'):
                _update(actions, connection, 'agent_runs', row, {'user_id': None}, 'null orphan agent user')
        orphan_projects = set()
        for table in ('deck_versions','deck_visual_systems','page_visual_plans','generation_jobs'):
            if table in tables:
                orphan_projects.update(row[0] for row in connection.execute(f'SELECT DISTINCT project_id FROM {_q(table)} WHERE project_id NOT IN (SELECT id FROM projects)'))
        for project_id in orphan_projects:
            deck_ids = {row['id'] for row in _rows(connection,'deck_versions','project_id=?',(project_id,))} if 'deck_versions' in tables else set()
            slide_ids = {row['id'] for row in _rows(connection,'slide_versions',f"deck_version_id IN ({','.join('?' for _ in deck_ids)})",tuple(deck_ids))} if deck_ids and 'slide_versions' in tables else set()
            for table in ('generation_jobs','page_visual_plans','deck_visual_systems','slide_versions','deck_versions'):
                if table not in tables: continue
                columns = _columns(connection, table); terms=[]; params=[]
                if 'project_id' in columns: terms.append('project_id=?'); params.append(project_id)
                if deck_ids and 'deck_version_id' in columns: terms.append(f"deck_version_id IN ({','.join('?' for _ in deck_ids)})"); params.extend(deck_ids)
                if slide_ids and 'slide_version_id' in columns: terms.append(f"slide_version_id IN ({','.join('?' for _ in slide_ids)})"); params.extend(slide_ids)
                for row in _rows(connection, table, ' OR '.join(terms), tuple(params)) if terms else []:
                    if table == 'generation_jobs' and str(row.get('status','')).upper() not in TERMINAL:
                        blockers.append(f"non-terminal GenerationJob {row.get('id')} in orphan graph")
                    _delete(actions, connection, table, row)
        selected = {(action['table'], json.dumps(action['pk'], sort_keys=True)) for action in actions.values() if action['action']=='delete'}
        for violation in connection.execute('PRAGMA foreign_key_check'):
            if violation[0] in AGENT_TABLES:
                row = connection.execute(f'SELECT rowid,* FROM {_q(violation[0])} WHERE rowid=?',(violation[1],)).fetchone()
                if row and (violation[0],json.dumps(_pk(connection,violation[0],_row(row)),sort_keys=True)) not in selected:
                    blockers.append(f'{violation[0]} rowid={violation[1]} has recoverable parent mismatch')
        ordered = sorted(actions.values(), key=lambda item: (item['action']=='delete', item['table'], json.dumps(item['pk'],sort_keys=True)))
        with sqlite3.connect(':memory:') as simulated:
            simulated.row_factory=sqlite3.Row; connection.backup(simulated); simulated.execute('PRAGMA foreign_keys=OFF'); _execute(simulated,ordered); after=_snapshot(simulated)
        if after['integrity'] != ['ok'] or after['foreign_keys'] or after['ownerless']: blockers.append('post-repair integrity/ownership would remain invalid')
        if after['credit'].get('invalid_accounts') or after['credit'].get('duplicate_task_entry_types'): blockers.append('credit invariants are invalid')
        if before['credit'].get('accounts_fingerprint') != after['credit'].get('accounts_fingerprint') or before['credit'].get('ledger_fingerprint') != after['credit'].get('ledger_fingerprint'): blockers.append('repair would change credit financial values')
        plan={'version':1,'created_at':datetime.now(timezone.utc).isoformat(),'database':str(database.resolve()),'database_fingerprint':_database_fingerprint(connection),'owner_mappings':mappings,'actions':ordered,'blockers':sorted(set(blockers)),'before':before,'expected_after':after}
    plan['plan_hash']=_hash_plan(plan); output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as archive:
        archive.write(json.dumps(plan,ensure_ascii=False,indent=2,sort_keys=True).encode())
    return plan


def load_repair_plan(path: Path) -> dict:
    with gzip.open(path,'rt',encoding='utf-8') as handle: plan=json.load(handle)
    if plan.get('plan_hash') != _hash_plan(plan): raise RepairBlocked('invalid plan hash')
    return plan


def apply_repair_plan(database: Path, plan_path: Path, confirmed_hash: str) -> dict:
    plan=load_repair_plan(plan_path)
    if confirmed_hash != plan['plan_hash']: raise RepairBlocked('confirmation hash mismatch')
    if plan['blockers']: raise RepairBlocked('; '.join(plan['blockers']))
    connection=sqlite3.connect(database,timeout=0,isolation_level=None); connection.row_factory=sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=OFF'); connection.execute('BEGIN IMMEDIATE')
        if _database_fingerprint(connection) != plan['database_fingerprint'] or _snapshot(connection) != plan['before']: raise RepairBlocked('database drift detected')
        for action in plan['actions']:
            clause,values=_where(action['pk']); row=connection.execute(f'SELECT rowid,* FROM {_q(action["table"])} WHERE {clause}',values).fetchone()
            if not row or _fingerprint(_row(row)) != action['row_fingerprint']: raise RepairBlocked(f'row drift: {action["table"]}')
        _execute(connection,plan['actions']); after=_snapshot(connection)
        if after != plan['expected_after'] or after['integrity'] != ['ok'] or after['foreign_keys'] or after['ownerless']: raise RepairBlocked('post-repair validation failed')
        connection.execute('COMMIT'); return {'plan_hash':plan['plan_hash'],'actions_applied':len(plan['actions']),'after':after}
    except Exception:
        if connection.in_transaction: connection.execute('ROLLBACK')
        raise
    finally: connection.close()


def _closed(database: Path) -> None:
    lsof=shutil.which('lsof')
    if sys.platform=='darwin' and not lsof: raise RepairBlocked('lsof required on macOS')
    if lsof:
        for path in (database,Path(str(database)+'-wal'),Path(str(database)+'-shm')):
            if path.exists() and subprocess.run([lsof,'-t','--',str(path)],capture_output=True,text=True).stdout.strip(): raise RepairBlocked(f'open handle: {path}')
    if database.exists():
        probe=sqlite3.connect(database,timeout=0,isolation_level=None)
        try: probe.execute('BEGIN EXCLUSIVE'); probe.execute('ROLLBACK')
        except sqlite3.OperationalError as exc: raise RepairBlocked(f'database busy: {database}') from exc
        finally: probe.close()


def restore_database(backup: Path, database: Path, quarantine: Path) -> dict:
    if not backup.is_file(): raise FileNotFoundError(backup)
    if quarantine.exists(): raise FileExistsError(quarantine)
    manifest_path = backup.with_suffix(backup.suffix + '.manifest.json')
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        expected_sha = manifest.get('database_sha256')
        if not expected_sha or expected_sha != _sha256(backup):
            raise RepairBlocked('backup manifest SHA-256 mismatch')
    _closed(database); temporary=Path(str(database)+'.restore-tmp')
    if temporary.exists(): raise FileExistsError(temporary)
    quarantine.mkdir(parents=True); moved=[]
    try:
        for current in (database,Path(str(database)+'-wal'),Path(str(database)+'-shm')):
            if current.exists(): target=quarantine/current.name; current.replace(target); moved.append((target,current))
        with _ro(backup) as source, sqlite3.connect(temporary) as target:
            source.backup(target)
        audit,_=audit_database(temporary)
        # A safety backup must be restorable even when it intentionally
        # preserves legacy FK violations for the subsequent repair plan.
        if audit['integrity_check'] != ['ok']:
            raise RepairBlocked('invalid backup')
        temporary.replace(database)
        restored_sha = _sha256(database)
    except Exception:
        temporary.unlink(missing_ok=True)
        if moved and database.exists():
            database.unlink()
        for source,target in reversed(moved): source.replace(target)
        try:
            quarantine.rmdir()
        except OSError:
            pass
        raise
    return {'database':str(database.resolve()),'backup':str(backup.resolve()),'quarantine':str(quarantine.resolve()),'sha256':restored_sha,'audit':audit}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__); subs=parser.add_subparsers(dest='command',required=True)
    p=subs.add_parser('audit'); p.add_argument('--database',required=True,type=Path)
    p=subs.add_parser('backup'); p.add_argument('--database',required=True,type=Path); p.add_argument('--output',required=True,type=Path); p.add_argument('--uploads',type=Path)
    p=subs.add_parser('repair-plan'); p.add_argument('--database',required=True,type=Path); p.add_argument('--output',required=True,type=Path); p.add_argument('--owner',action='append',default=[])
    p=subs.add_parser('repair-apply'); p.add_argument('--database',required=True,type=Path); p.add_argument('--plan',required=True,type=Path); p.add_argument('--confirm-plan-hash',required=True)
    p=subs.add_parser('restore'); p.add_argument('--backup',required=True,type=Path); p.add_argument('--database',required=True,type=Path); p.add_argument('--quarantine',required=True,type=Path)
    args=parser.parse_args()
    try:
        if args.command=='audit': result,blocked=audit_database(args.database); print(json.dumps(result,ensure_ascii=False,indent=2)); return 2 if blocked else 0
        if args.command=='backup': result=backup_database(args.database,args.output,args.uploads)
        elif args.command=='repair-plan': result=create_repair_plan(args.database,args.output,parse_owner_specs(args.owner))
        elif args.command=='repair-apply': result=apply_repair_plan(args.database,args.plan,args.confirm_plan_hash)
        else: result=restore_database(args.backup,args.database,args.quarantine)
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0
    except (OSError,ValueError,RepairBlocked,sqlite3.Error) as exc: print(f'db_safety: {exc}',file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
