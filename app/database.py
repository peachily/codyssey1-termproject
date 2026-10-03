import os
from collections.abc import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.getenv("DATABASE_URL") or "sqlite:///./chatbot.db"
    database_engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(database_engine, "connect")
    def configure_sqlite(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return database_engine


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def initialize_database(target_engine: Engine = engine) -> None:
    """Create missing tables after application models have been imported."""
    Base.metadata.create_all(bind=target_engine)
