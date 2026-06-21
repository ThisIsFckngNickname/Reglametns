from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.core.exceptions import ConflictException, NotFoundException
from app.database import get_db
from app.models.company import Company
from app.models.user import User
from app.models.user_company import UserCompany
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
async def list_companies(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список всех компаний. Требует аутентификации."""
    stmt = select(Company).order_by(Company.id)
    result = await db.execute(stmt)
    companies = result.scalars().all()
    return [CompanyResponse.model_validate(c) for c in companies]


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Получить компанию по ID."""
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise NotFoundException(message="Компания не найдена")
    return CompanyResponse.model_validate(company)


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    body: CompanyCreate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать компанию (только админ)."""
    stmt = select(Company).where(Company.name == body.name)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise ConflictException(message="Компания с таким названием уже существует", field="name")

    company = Company(
        name=body.name,
        inn=body.inn,
        legal_form=body.legal_form,
        document_structure=body.document_structure,
        style_settings=body.style_settings,
        use_gost=body.use_gost,
    )
    db.add(company)
    await db.flush()

    # Админ автоматически добавляется в созданную компанию
    user_company = UserCompany(
        user_id=admin.id,
        company_id=company.id,
        role="admin",
    )
    db.add(user_company)

    await db.flush()
    return CompanyResponse.model_validate(company)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int,
    body: CompanyUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Обновить компанию (только админ)."""
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise NotFoundException(message="Компания не найдена")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(company, field, value)

    return CompanyResponse.model_validate(company)


@router.delete("/{company_id}", status_code=200)
async def delete_company(
    company_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Удалить компанию (только админ)."""
    stmt = select(Company).where(Company.id == company_id)
    result = await db.execute(stmt)
    company = result.scalar_one_or_none()
    if not company:
        raise NotFoundException(message="Компания не найдена")

    # Удаляем связи пользователей с компанией
    links_stmt = select(UserCompany).where(UserCompany.company_id == company_id)
    links_result = await db.execute(links_stmt)
    for link in links_result.scalars().all():
        await db.delete(link)

    await db.delete(company)
    return {"message": "Компания удалена"}
