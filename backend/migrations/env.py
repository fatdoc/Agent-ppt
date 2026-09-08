import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add the backend directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    # Alembic may run inside the test/application process. Do not silently
    # disable service loggers that were created before this module loaded.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# target_metadata is used for autogenerate support.
target_metadata = db.metadata


def get_url() -> str:
    """Resolve the migration target without importing the Flask application."""
    env_url = (os.getenv("DATABASE_URL") or "").strip()
    if env_url:
        return env_url

    configured_url = (config.get_main_option("sqlalchemy.url") or "").strip()
    if configured_url and configured_url != "sqlite:///placeholder.db":
        return configured_url

    raise RuntimeError(
        "DATABASE_URL must be set explicitly for migrations; refusing placeholder database"
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Several historical SQLite revisions use Alembic batch mode, which
        # rebuilds parent tables while child tables still exist. Keep FK
        # enforcement off only for this dedicated migration connection;
        # integrity is explicitly checked by the bridge preflight and runtime
        # application connections enable it again.
        if connection.dialect.name == 'sqlite':
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            # End SQLAlchemy's implicit transaction so Alembic owns and
            # commits the migration/version-table transaction below.
            connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
