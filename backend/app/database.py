"""
Настройка базы данных SQLite.
- WAL mode для производительности
- sync SQLAlchemy (достаточно для одного пользователя)
- get_db dependency для FastAPI
"""

import logging
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

logger = logging.getLogger(__name__)

# Создание engine с WAL mode для SQLite
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Включаем WAL mode и оптимизации SQLite при подключении."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Создание всех таблиц (если не существуют)."""
    import app.models  # noqa: F401 — импорт для регистрации моделей
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")


def get_db():
    """FastAPI dependency: получение сессии БД.

    Используется как Generator для автоматического закрытия сессии.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
