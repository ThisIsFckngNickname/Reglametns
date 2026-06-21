from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, get_db
from app.core.exceptions import ConflictException, NotFoundException, BadRequestException
from app.core.security import hash_password
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding
from app.schemas.user import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    SetHoldingRequest,
    SetHoldingResponse,
    UserHoldingInfo,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/user", tags=["user"])


# ---- Админские эндпоинты ----


@router.get("/admin/users", response_model=list[AdminUserResponse])
async def admin_list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Список всех пользователей (только админ)."""
    stmt = select(User).order_by(User.id)
    result = await db.execute(stmt)
    users = result.scalars().all()

    response = []
    for user in users:
        holdings_stmt = select(
            UserHolding.holding_id,
            Holding.name,
            UserHolding.role,
        ).join(Holding, UserHolding.holding_id == Holding.id).where(
            UserHolding.user_id == user.id
        )
        holdings_result = await db.execute(holdings_stmt)
        holdings = [
            UserHoldingInfo(holding_id=h.holding_id, holding_name=h.name, role=h.role)
            for h in holdings_result
        ]

        active_holding = None
        if user.active_holding:
            from app.schemas.holding import HoldingBrief
            active_holding = HoldingBrief.model_validate(user.active_holding)

        response.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            active_holding=active_holding,
            holdings=holdings,
            created_at=user.created_at,
        ))

    return response


@router.post("/admin/users", response_model=AdminUserResponse, status_code=201)
async def admin_create_user(
    body: AdminUserCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать пользователя (только админ)."""
    # Проверка дубликата email
    stmt = select(User).where(User.email == body.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise ConflictException(message="Пользователь с таким email уже существует", field="email")

    user = User(email=body.email, is_verified=True)
    user.set_password(body.password)
    db.add(user)
    await db.flush()

    # Если указан holding, добавляем пользователя в него
    holding_id = body.holding_id
    role = body.role
    created_holding = None

    if holding_id:
        holding_stmt = select(Holding).where(Holding.id == holding_id)
        holding_result = await db.execute(holding_stmt)
        holding = holding_result.scalar_one_or_none()
        if not holding:
            raise NotFoundException(message="Холдинг не найден", field="holding_id")

        user_holding = UserHolding(
            user_id=user.id,
            holding_id=holding.id,
            role=role,
        )
        db.add(user_holding)
        user.active_holding_id = holding.id
        created_holding = holding
    else:
        # Если холдинг не указан, используем первый доступный
        first_holding_stmt = select(Holding).order_by(Holding.id).limit(1)
        first_holding_result = await db.execute(first_holding_stmt)
        first_holding = first_holding_result.scalar_one_or_none()
        if first_holding:
            user_holding = UserHolding(
                user_id=user.id,
                holding_id=first_holding.id,
                role=role,
            )
            db.add(user_holding)
            user.active_holding_id = first_holding.id
            created_holding = first_holding

    await db.flush()

    from app.schemas.holding import HoldingBrief
    active_holding = HoldingBrief.model_validate(created_holding) if created_holding else None

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        active_holding=active_holding,
        holdings=[UserHoldingInfo(
            holding_id=created_holding.id,
            holding_name=created_holding.name,
            role=role,
        )] if created_holding else [],
        created_at=user.created_at,
    )


@router.put("/admin/users/{user_id}", response_model=AdminUserResponse)
async def admin_update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Обновить данные пользователя (только админ)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundException(message="Пользователь не найден", field="user_id")

    if body.email is not None:
        user.email = body.email
    if body.password is not None:
        user.set_password(body.password)
    if body.is_verified is not None:
        user.is_verified = body.is_verified

    await db.flush()

    # Load holdings
    holdings_stmt = select(
        UserHolding.holding_id,
        Holding.name,
        UserHolding.role,
    ).join(Holding, UserHolding.holding_id == Holding.id).where(
        UserHolding.user_id == user.id
    )
    holdings_result = await db.execute(holdings_stmt)
    holdings = [
        UserHoldingInfo(holding_id=h.holding_id, holding_name=h.name, role=h.role)
        for h in holdings_result
    ]

    from app.schemas.holding import HoldingBrief
    active_holding = HoldingBrief.model_validate(user.active_holding) if user.active_holding else None

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        active_holding=active_holding,
        holdings=holdings,
        created_at=user.created_at,
    )


@router.delete("/admin/users/{user_id}", status_code=200)
async def admin_delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Удалить пользователя (только админ)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise NotFoundException(message="Пользователь не найден", field="user_id")

    # Удаляем связи с холдингами
    delete_links = select(UserHolding).where(UserHolding.user_id == user_id)
    links_result = await db.execute(delete_links)
    for link in links_result.scalars().all():
        await db.delete(link)

    await db.delete(user)
    return {"message": "Пользователь удалён"}


@router.put("/admin/users/{user_id}/ban", status_code=200)
async def admin_ban_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Заблокировать пользователя (только админ)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="Пользователь не найден", field="user_id")
    if user.is_banned:
        raise BadRequestException(code="ALREADY_BANNED", message="Пользователь уже заблокирован")
    user.is_banned = True
    await db.flush()
    return {"message": f"Пользователь {user.email} заблокирован"}


@router.put("/admin/users/{user_id}/unban", status_code=200)
async def admin_unban_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Разблокировать пользователя (только админ)."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="Пользователь не найден", field="user_id")
    if not user.is_banned:
        raise BadRequestException(code="NOT_BANNED", message="Пользователь не заблокирован")
    user.is_banned = False
    await db.flush()
    return {"message": f"Пользователь {user.email} разблокирован"}


@router.put("/admin/users/{user_id}/holdings/{holding_id}", status_code=200)
async def admin_set_user_holding_role(
    user_id: int,
    holding_id: int,
    role: str = "user",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Назначить пользователю роль в холдинге (только админ)."""
    # Проверка пользователя
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="Пользователь не найден", field="user_id")

    # Проверка холдинга
    holding_stmt = select(Holding).where(Holding.id == holding_id)
    holding_result = await db.execute(holding_stmt)
    holding = holding_result.scalar_one_or_none()
    if not holding:
        raise NotFoundException(message="Холдинг не найден", field="holding_id")

    # Проверка существующей связи
    link_stmt = select(UserHolding).where(
        UserHolding.user_id == user_id,
        UserHolding.holding_id == holding_id,
    )
    link_result = await db.execute(link_stmt)
    link = link_result.scalar_one_or_none()

    if link:
        link.role = role
    else:
        link = UserHolding(user_id=user_id, holding_id=holding_id, role=role)
        db.add(link)

    return {"message": f"Роль {role} назначена пользователю в холдинге {holding.name}"}


# ---- Пользовательские эндпоинты ----


@router.put("/holding", response_model=SetHoldingResponse)
async def set_active_holding(
    body: SetHoldingRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the active holding for the current user."""
    svc = AuthService(db=db)
    result = await svc.set_active_holding(user.id, body.holding_id)
    return result
