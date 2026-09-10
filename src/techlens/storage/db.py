"""
Database engine, session factory, and helper context managers for SQLite via SQLAlchemy.
Call init_db() once at startup to create tables; use get_session() for all DB writes.
Includes _ensure_column() for migration-safe ALTER TABLE on existing databases.
"""

import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from techlens.config import settings
from techlens.storage.models import Base

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # SQLite only
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _ensure_column(table: str, column: str, col_def: str) -> None:
    """
    Add a column to an existing table if it does not already exist.
    Silently ignores OperationalError (duplicate column) so it is safe to call
    every startup. Only needed for existing DBs — new DBs get the column via
    Base.metadata.create_all().

    Args:
        table:   Table name (e.g. "articles").
        column:  Column name (e.g. "concepts_extracted").
        col_def: SQLite column definition (e.g. "BOOLEAN DEFAULT 0 NOT NULL").
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
            conn.commit()
            logger.info("Migration: added column %s.%s", table, column)
    except OperationalError:
        # Column already exists — nothing to do
        pass


def init_db() -> None:
    """Create all tables and apply any pending column migrations for existing DBs."""
    Base.metadata.create_all(bind=engine)
    # Migration-safe: add concepts_extracted to articles table if missing
    _ensure_column("articles", "concepts_extracted", "BOOLEAN NOT NULL DEFAULT 0")
    logger.info("Database initialized")



@contextmanager
def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency."""
    with get_session() as session:
        yield session
