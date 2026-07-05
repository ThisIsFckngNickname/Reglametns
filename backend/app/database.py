"""
Настройка базы данных SQLite.
- WAL mode для производительности
- sync SQLAlchemy (достаточно для одного пользователя)
- get_db dependency для FastAPI
"""

import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _run_migrations():
    """Apply schema migrations for existing databases."""
    import sqlalchemy as sa
    insp = sa.inspect(engine)
    columns = [c["name"] for c in insp.get_columns("document_analyses")]
    if "cancelled" not in columns:
        logger.info("Migration: adding cancelled column to document_analyses")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE document_analyses ADD COLUMN cancelled INTEGER DEFAULT 0"))
            conn.commit()
            logger.info("Migration complete: cancelled column added")


def init_db():
    import app.models
    Base.metadata.create_all(bind=engine)
    _run_migrations()
    logger.info("Database tables created successfully")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
