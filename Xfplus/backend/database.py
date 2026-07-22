from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_runtime_columns()


def ensure_runtime_columns() -> None:
    """Apply tiny SQLite-safe additive migrations used by the v1 demo runtime."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "incidents" not in table_names:
        return
    incident_columns = {column["name"] for column in inspector.get_columns("incidents")}
    incident_migrations = {
        "need_review": "ALTER TABLE incidents ADD COLUMN need_review BOOLEAN DEFAULT 0",
        "source_title": "ALTER TABLE incidents ADD COLUMN source_title VARCHAR(240) DEFAULT ''",
        "source_org": "ALTER TABLE incidents ADD COLUMN source_org VARCHAR(120) DEFAULT ''",
        "source_url": "ALTER TABLE incidents ADD COLUMN source_url TEXT DEFAULT ''",
        "source_date": "ALTER TABLE incidents ADD COLUMN source_date VARCHAR(40) DEFAULT ''",
        "workflow_steps": "ALTER TABLE incidents ADD COLUMN workflow_steps TEXT DEFAULT '[]'",
    }
    with engine.begin() as connection:
        for column, statement in incident_migrations.items():
            if column not in incident_columns:
                connection.execute(text(statement))

    if "messages" not in table_names:
        return
    message_columns = {column["name"] for column in inspector.get_columns("messages")}
    message_migrations = {
        "target_user_id": "ALTER TABLE messages ADD COLUMN target_user_id INTEGER",
        "parent_id": "ALTER TABLE messages ADD COLUMN parent_id INTEGER",
        "status": "ALTER TABLE messages ADD COLUMN status VARCHAR(40) DEFAULT 'sent'",
        "reply_content": "ALTER TABLE messages ADD COLUMN reply_content TEXT DEFAULT ''",
        "review_note": "ALTER TABLE messages ADD COLUMN review_note TEXT DEFAULT ''",
        "reviewed_by": "ALTER TABLE messages ADD COLUMN reviewed_by INTEGER",
        "reviewed_at": "ALTER TABLE messages ADD COLUMN reviewed_at VARCHAR(40)",
        "attachments": "ALTER TABLE messages ADD COLUMN attachments TEXT DEFAULT '[]'",
    }
    with engine.begin() as connection:
        for column, statement in message_migrations.items():
            if column not in message_columns:
                connection.execute(text(statement))
