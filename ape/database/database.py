"""Database engine, session management and health checks."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from ape.core.exceptions import DatabaseError
from ape.core.settings import SETTINGS
from ape.database.base import Base
from ape.utils.logger import logger


class DatabaseManager:
    """Own the SQLAlchemy engine and transaction lifecycle."""

    def __init__(self, database_file: Path | str | None = None, echo: bool = False) -> None:
        self.database_file = Path(database_file or SETTINGS.database_file)
        self.database_file.parent.mkdir(parents=True, exist_ok=True)

        database_url = f"sqlite:///{self.database_file.as_posix()}"
        self.engine: Engine = create_engine(
            database_url,
            echo=echo,
            future=True,
            connect_args={"check_same_thread": False},
        )
        self._configure_sqlite()
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

    def _configure_sqlite(self) -> None:
        """Enable safe SQLite settings for every new connection."""

        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    def initialize(self) -> None:
        """Create all registered tables if they do not already exist."""
        try:
            # Import models so SQLAlchemy registers them on Base.metadata.
            from ape.database import models  # noqa: F401

            Base.metadata.create_all(self.engine)
            logger.info("Database initialized: %s", self.database_file)
        except Exception as exc:
            logger.exception("Database initialization failed.")
            raise DatabaseError(f"Could not initialize database: {exc}") from exc

    def drop_all(self) -> None:
        """Drop every APE table. Intended for tests and controlled resets only."""
        try:
            Base.metadata.drop_all(self.engine)
            logger.warning("All database tables were dropped: %s", self.database_file)
        except Exception as exc:
            raise DatabaseError(f"Could not drop database tables: {exc}") from exc

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional session with automatic commit or rollback."""
        db_session = self.session_factory()
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            logger.exception("Database transaction rolled back.")
            raise
        finally:
            db_session.close()

    def health_check(self) -> bool:
        """Return True when SQLite accepts a trivial query."""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("Database health check failed.")
            return False

    def table_names(self) -> list[str]:
        """Return all current table names in deterministic order."""
        return sorted(inspect(self.engine).get_table_names())

    def dispose(self) -> None:
        """Release all pooled database connections."""
        self.engine.dispose()


DATABASE = DatabaseManager()
