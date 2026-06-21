from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin, get_db
from app.core.exceptions import ConflictException, NotFoundException, BadRequestException
from app.core.security import hash_password
from app.models.company import Company
from app.models.user import User
from app.models.user_company import UserCompany
from app.schemas.user import (
    AdminUserCreate,
    AdminUserResponse,
    AdminUserUpdate,
    SetCompanyRequest,
    SetCompanyResponse,
    UserCompanyInfo,
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
        companies_stmt = select(
            UserCompany.company_id,
            Company.name,
            UserCompany.role,
        ).join(Company, UserCompany.company_id == Company.id).where(
            UserCompany.user_id == user.id
        )
        companies_result = await db.execute(companies_stmt)
        companies = [
            UserCompanyInfo(company_id=c.company_id, company_name=c.name, role=c.role)
            for c in companies_result
        ]

        active_company = None
        if user.active_company:
            from app.schemas.company import CompanyBrief
            active_company = CompanyBrief.model_validate(user.active_company)

        response.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            active_company=active_company,
            companies=companies,
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

    # Если указана компания, добавляем пользователя в неё
    company_id = body.company_id
    role = body.role
    created_company = None

    if company_id:
        company_stmt = select(Company).where(Company.id == company_id)
        company_result = await db.execute(company_stmt)
        company = company_result.scalar_one_or_none()
        if not company:
            raise NotFoundException(message="Компания не найдена", field="company_id")

        user_company = UserCompany(
            user_id=user.id,
            company_id=company.id,
            role=role,
        )
        db.add(user_company)
        user.active_company_id = company.id
        created_company = company
    else:
        # Если компания не указана, используем первую доступную
        first_company_stmt = select(Company).order_by(Company.id).limit(1)
        first_company_result = await db.execute(first_company_stmt)
        first_company = first_company_result.scalar_one_or_none()
        if first_company:
            user_company = UserCompany(
                user_id=user.id,
                company_id=first_company.id,
                role=role,
            )
            db.add(user_company)
            user.active_company_id = first_company.id
            created_company = first_company

    await db.flush()

    from app.schemas.company import CompanyBrief
    active_company = CompanyBrief.model_validate(created_company) if created_company else None

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        active_company=active_company,
        companies=[UserCompanyInfo(
            company_id=created_company.id,
            company_name=created_company.name,
            role=role,
        )] if created_company else [],
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

    # Load companies
    companies_stmt = select(
        UserCompany.company_id,
        Company.name,
        UserCompany.role,
    ).join(Company, UserCompany.company_id == Company.id).where(
        UserCompany.user_id == user.id
    )
    companies_result = await db.execute(companies_stmt)
    companies = [
        UserCompanyInfo(company_id=c.company_id, company_name=c.name, role=c.role)
        for c in companies_result
    ]

    from app.schemas.company import CompanyBrief
    active_company = CompanyBrief.model_validate(user.active_company) if user.active_company else None

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        active_company=active_company,
        companies=companies,
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

    # Удаляем связи с компаниями
    delete_links = select(UserCompany).where(UserCompany.user_id == user_id)
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


@router.put("/admin/users/{user_id}/companies/{company_id}", status_code=200)
async def admin_set_user_company_role(
    user_id: int,
    company_id: int,
    role: str = "user",
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Назначить пользователю роль в компании (только админ)."""
    # Проверка пользователя
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if not user:
        raise NotFoundException(message="Пользователь не найден", field="user_id")

    # Проверка компании
    company_stmt = select(Company).where(Company.id == company_id)
    company_result = await db.execute(company_stmt)
    company = company_result.scalar_one_or_none()
    if not company:
        raise NotFoundException(message="Компания не найдена", field="company_id")

    # Проверка существующей связи
    link_stmt = select(UserCompany).where(
        UserCompany.user_id == user_id,
        UserCompany.company_id == company_id,
    )
    link_result = await db.execute(link_stmt)
    link = link_result.scalar_one_or_none()

    if link:
        link.role = role
    else:
        link = UserCompany(user_id=user_id, company_id=company_id, role=role)
        db.add(link)

    return {"message": f"Роль {role} назначена пользователю в компании {company.name}"}


# ---- Пользовательские эндпоинты ----


@router.put("/company", response_model=SetCompanyResponse)
async def set_active_company(
    body: SetCompanyRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the active company for the current user."""
    svc = AuthService(db=db)
    result = await svc.set_active_company(user.id, body.company_id)
    return result
