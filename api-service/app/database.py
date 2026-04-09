"""
Database configuration and session management.
"""
from __future__ import annotations

import logging
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


def get_engine():
    """Create database engine with appropriate settings for the database type."""
    db_url = settings.DATABASE_URL

    if db_url.startswith("sqlite"):
        # SQLite doesn't support pool_size/max_overflow
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    else:
        # PostgreSQL — avoid hanging forever when the server is down or unreachable
        engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args={"connect_timeout": 10, "client_encoding": "utf8"},
            echo=settings.DEBUG,
        )

    return engine


# Create database engine
engine = get_engine()

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function that provides a database session.
    Yields a session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.
    This is useful for development and testing.
    """
    from app.models import Base
    logger.info("init_db: inspecting database schema")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    managed_tables = set(Base.metadata.tables.keys())
    has_user_tables = bool(table_names & managed_tables)
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    logger.info(
        "init_db: database inspected is_sqlite=%s has_user_tables=%s table_count=%s managed_table_count=%s",
        is_sqlite,
        has_user_tables,
        len(table_names),
        len(managed_tables),
    )

    if is_sqlite:
        logger.info("init_db: sqlite create_all begin")
        Base.metadata.create_all(bind=engine)
        logger.info("init_db: sqlite create_all done")
        return

    if has_user_tables:
        logger.info("init_db: existing schema detected, running alembic upgrade")
        _upgrade_existing_schema()
    else:
        logger.info("init_db: empty schema detected, running create_all + stamp")
        Base.metadata.create_all(bind=engine)
        _stamp_schema_head()

    # Keep create_all as a final safety net for unmanaged local environments.
    logger.info("init_db: final create_all safety pass begin")
    Base.metadata.create_all(bind=engine)
    logger.info("init_db: final create_all safety pass done")


def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    from app.models import Base

    Base.metadata.drop_all(bind=engine)


def _upgrade_existing_schema() -> None:
    try:
        command = _load_alembic_command_module()
        command.upgrade(_alembic_config(), "head")
        logger.info("Database migrations upgraded to head.")
    except Exception:
        logger.exception("Failed to upgrade database schema to head.")
        raise


def _stamp_schema_head() -> None:
    try:
        command = _load_alembic_command_module()
        command.stamp(_alembic_config(), "head")
        logger.info("Database schema stamped at head.")
    except Exception:
        logger.exception("Failed to stamp database schema at head.")
        raise


def _alembic_config():
    Config = _load_alembic_config_class()

    api_root = Path(__file__).resolve().parents[1]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return config


def _load_alembic_command_module():
    with _site_alembic_import_scope():
        from alembic import command

    return command


def _load_alembic_config_class():
    with _site_alembic_import_scope():
        from alembic.config import Config

    return Config


@contextmanager
def _site_alembic_import_scope():
    api_root = Path(__file__).resolve().parents[1]
    removed_entries: list[tuple[int, str]] = []
    removed_modules = {}

    for index in range(len(sys.path) - 1, -1, -1):
        entry = sys.path[index]
        if _path_points_to_api_root(entry, api_root):
            removed_entries.append((index, entry))
            sys.path.pop(index)

    for module_name in ("alembic", "alembic.config", "alembic.command"):
        module = sys.modules.pop(module_name, None)
        if module is not None:
            removed_modules[module_name] = module

    try:
        yield
    finally:
        for index, entry in sorted(removed_entries, key=lambda item: item[0]):
            sys.path.insert(index, entry)
        sys.modules.update(removed_modules)


def _path_points_to_api_root(entry: str, api_root: Path) -> bool:
    if entry == "":
        return Path.cwd().resolve() == api_root
    try:
        return Path(entry).resolve() == api_root
    except OSError:
        return False
