from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.exceptions import ConflictException, NotFoundException
from app.database import get_db
from app.models.holding import Holding
from app.models.user import User
from app.models.user_holding import UserHolding
from app.schemas.holding import HoldingCreate, HoldingResponse, HoldingUpdate

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("", response_model=list[HoldingResponse])
async def list_holdings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список всех холдингов. Требует аутентификации."""
    stmt = select(Holding).order_by(Holding.id)
    result = await db.execute(stmt)
    holdings = result.scalars().all()
    return [HoldingResponse.model_validate(h) for h in holdings]


@router.get("/{holding_id}", response_model=HoldingResponse)
async def get_holding(
    holding_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить холдинг по ID."""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()
    if not holding:
        raise NotFoundException(message="Холдинг не найден")
    return HoldingResponse.model_validate(holding)


@router.post("", response_model=HoldingResponse, status_code=201)
async def create_holding(
    body: HoldingCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать холдинг (только админ)."""
    stmt = select(Holding).where(Holding.name == body.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise ConflictException(message="Холдинг с таким названием уже существует", field="name")

    holding = Holding(
        name=body.name,
        inn=body.inn,
        legal_form=body.legal_form,
        document_structure=body.document_structure,
        style_settings=body.style_settings,
        use_gost=body.use_gost,
    )
    db.add(holding)
    await db.flush()

    # Админ автоматически добавляется в созданный холдинг
    user_holding = UserHolding(
        user_id=admin.id,
        holding_id=holding.id,
        role="admin",
    )
    db.add(user_holding)

    await db.flush()
    return HoldingResponse.model_validate(holding)


@router.put("/{holding_id}", response_model=HoldingResponse)
async def update_holding(
    holding_id: int,
    body: HoldingUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Обновить холдинг (только админ)."""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()
    if not holding:
        raise NotFoundException(message="Холдинг не найден")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(holding, field, value)

    return HoldingResponse.model_validate(holding)


@router.delete("/{holding_id}", status_code=200)
async def delete_holding(
    holding_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Удалить холдинг (только админ)."""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()
    if not holding:
        raise NotFoundException(message="Холдинг не найден")

    # Удаляем связи пользователей с холдингом
    links_stmt = select(UserHolding).where(UserHolding.holding_id == holding_id)
    links_result = await db.execute(links_stmt)
    for link in links_result.scalars().all():
        await db.delete(link)

    await db.delete(holding)
    return {"message": "Холдинг удалён"}
