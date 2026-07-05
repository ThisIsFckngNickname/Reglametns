"""
company_profile_service — CRUD для профилей компании.

Функции:
- create_profile — создание нового профиля
- get_profile — получение профиля по ID
- list_profiles — список профилей с пагинацией и фильтрацией
- delete_profile — удаление профиля (каскадно удаляет документы и параграфы)
- update_profile_status — обновление статуса обработки профиля
"""

import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.company_profile import CompanyProfile

logger = logging.getLogger(__name__)


async def create_profile(
    db: Session,
    name: str,
    description: str = "",
) -> CompanyProfile:
    """
    Создать новый профиль компании.

    Args:
        db: Сессия SQLAlchemy.
        name: Название профиля.
        description: Описание профиля.

    Returns:
        Созданный объект CompanyProfile.
    """
    profile = CompanyProfile(
        name=name,
        description=description,
        profile_type="paragraph_logic",
        profile_json=json.dumps({}),
        status="uploaded",
        progress_pct=0,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    logger.info("Profile created: id=%s name=%s", profile.id, name)
    return profile


async def get_profile(
    db: Session,
    profile_id: str,
) -> CompanyProfile | None:
    """
    Получить профиль по ID (с загрузкой связанных документов и параграфов).

    Args:
        db: Сессия SQLAlchemy.
        profile_id: UUID профиля.

    Returns:
        Объект CompanyProfile или None, если не найден.
    """
    return (
        db.query(CompanyProfile)
        .filter(CompanyProfile.id == profile_id)
        .first()
    )


async def list_profiles(
    db: Session,
    status: str | None = None,
    profile_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[CompanyProfile], int]:
    """
    Получить список профилей с фильтрацией и пагинацией.

    Args:
        db: Сессия SQLAlchemy.
        status: Фильтр по статусу (например, 'ready').
        profile_type: Фильтр по типу профиля.
        limit: Максимальное количество записей.
        offset: Смещение от начала.

    Returns:
        Кортеж (список профилей, общее количество).
    """
    query = db.query(CompanyProfile)

    if status:
        query = query.filter(CompanyProfile.status == status)
    if profile_type:
        query = query.filter(CompanyProfile.profile_type == profile_type)

    total = query.count()

    profiles = (
        query.order_by(desc(CompanyProfile.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return profiles, total


async def delete_profile(
    db: Session,
    profile_id: str,
) -> bool:
    """
    Удалить профиль по ID (каскадно удаляет документы и параграфы).

    Args:
        db: Сессия SQLAlchemy.
        profile_id: UUID профиля.

    Returns:
        True, если профиль был удалён; False, если не найден.
    """
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.id == profile_id)
        .first()
    )
    if not profile:
        return False

    db.delete(profile)
    db.commit()
    logger.info("Profile deleted: id=%s name=%s", profile_id, profile.name)
    return True


async def update_profile_status(
    db: Session,
    profile_id: str,
    status: str,
    error_message: str | None = None,
    progress_pct: int | None = None,
) -> None:
    """
    Обновить статус обработки профиля.

    Args:
        db: Сессия SQLAlchemy.
        profile_id: UUID профиля.
        status: Новый статус.
        error_message: Текст ошибки (если status='failed').
        progress_pct: Прогресс обработки (0-100).
    """
    profile = (
        db.query(CompanyProfile)
        .filter(CompanyProfile.id == profile_id)
        .first()
    )
    if not profile:
        logger.warning(
            "Profile not found for status update: id=%s", profile_id
        )
        return

    profile.status = status
    profile.updated_at = datetime.utcnow

    if error_message is not None:
        profile.error_message = error_message

    if progress_pct is not None:
        profile.progress_pct = progress_pct

    db.commit()
    logger.info(
        "Profile status updated: id=%s status=%s progress=%s",
        profile_id,
        status,
        progress_pct,
    )
