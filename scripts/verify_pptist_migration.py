"""Migrate only isolated databases; never read a user's dotenv/database."""
import os,sys,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if not os.getenv('PPTIST_MIGRATION_ISOLATED'):
    with tempfile.TemporaryDirectory(prefix='pptist-migration-') as tmp:
        env={k:os.environ[k] for k in ('PATH','TMPDIR') if k in os.environ}
        env.update(PPTIST_MIGRATION_ISOLATED='1',LOAD_DOTENV='false',DATABASE_URL=f'sqlite:///{tmp}/migration.db',UPLOAD_FOLDER=f'{tmp}/uploads',HOME=tmp,SECRET_KEY='isolated-migration-secret-not-production')
        raise SystemExit(subprocess.call([sys.executable,__file__],env=env))
sys.path.insert(0,str(ROOT/'backend'))
from app import create_app
from models import db
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.autogenerate import compare_metadata
app=create_app({'TESTING':True})
with app.app_context():
    config=Config(str(ROOT/'backend/alembic.ini'))
    config.set_main_option('script_location',str(ROOT/'backend/migrations'))
    config.set_main_option('sqlalchemy.url',os.environ['DATABASE_URL'])
    command.upgrade(config,'030_batch01_safety_expand')
    command.upgrade(config,'head')
    with db.engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c,opts={'compare_type':True}),db.metadata)==[]
    command.downgrade(config,'030_batch01_safety_expand')
    command.upgrade(config,'head')
    with db.engine.connect() as c:
        assert compare_metadata(MigrationContext.configure(c,opts={'compare_type':True}),db.metadata)==[]
        assert c.exec_driver_sql('PRAGMA integrity_check').scalar()=='ok'
        assert not c.exec_driver_sql('PRAGMA foreign_key_check').fetchall()
    print('TEMP_DB: empty→030→031; 031→030→031; schema drift=[]; integrity=ok')
