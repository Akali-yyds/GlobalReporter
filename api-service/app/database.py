"""
Database configuration and session management.
"""
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


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

    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    """
    Drop all database tables.
    WARNING: This will delete all data!
    """
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
