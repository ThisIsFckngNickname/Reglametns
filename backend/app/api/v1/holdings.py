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
    """Get list of all holdings. Requires authentication."""
    stmt = select(Holding).order_by(Holding.id)
    result = await db.execute(stmt)
    holdings = result.scalars().all()
    return [
        HoldingResponse.model_validate(h) for h in holdings
    ]


@router.post("", response_model=HoldingResponse, status_code=201)
async def create_holding(
    body: HoldingCreate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new holding. Requires admin role."""
    # Check uniqueness
    stmt = select(Holding).where(Holding.name == body.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise ConflictException(
            message="A holding with this name already exists",
            field="name",
        )

    holding = Holding(
        name=body.name,
        inn=body.inn,
        legal_form=body.legal_form,
    )
    db.add(holding)
    await db.flush()

    return HoldingResponse.model_validate(holding)


@router.put("/{holding_id}", response_model=HoldingResponse)
async def update_holding(
    holding_id: int,
    body: HoldingUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update a holding. All fields are optional (partial update). Requires admin."""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()

    if holding is None:
        raise NotFoundException(
            message="Holding not found",
            field="holding_id",
        )

    # Check name uniqueness if name is being changed
    if body.name is not None and body.name != holding.name:
        dup_stmt = select(Holding).where(
            Holding.name == body.name,
            Holding.id != holding_id,
        )
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
            raise ConflictException(
                message="A holding with this name already exists",
                field="name",
            )

    if body.name is not None:
        holding.name = body.name
    if body.inn is not None:
        holding.inn = body.inn
    if body.legal_form is not None:
        holding.legal_form = body.legal_form
    if body.document_structure is not None:
        holding.document_structure = body.document_structure
    if body.style_settings is not None:
        holding.style_settings = body.style_settings
    if body.use_gost is not None:
        holding.use_gost = body.use_gost

    await db.flush()

    return HoldingResponse.model_validate(holding)


@router.delete("/{holding_id}", status_code=204)
async def delete_holding(
    holding_id: int,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a holding. Requires admin."""
    stmt = select(Holding).where(Holding.id == holding_id)
    result = await db.execute(stmt)
    holding = result.scalar_one_or_none()

    if holding is None:
        raise NotFoundException(
            message="Holding not found",
            field="holding_id",
        )

    # Check for existing user_holdings references
    ref_stmt = select(UserHolding).where(UserHolding.holding_id == holding_id).limit(1)
    ref_result = await db.execute(ref_stmt)
    if ref_result.scalar_one_or_none():
        raise ConflictException(
            message="Cannot delete holding with existing user associations",
        )

    await db.delete(holding)
    await db.flush()
