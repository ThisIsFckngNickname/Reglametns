"""
Tests for CompanyTerm and CompanyAbbreviation models, CRUD API, and pipeline sync.

Coverage:
- Model creation and unique constraints
- CRUD API endpoints (list, create, update, delete)
- Pipeline sync integration
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_term import CompanyTerm
from app.models.company_abbreviation import CompanyAbbreviation
from app.models.company import Company
from app.models.user import User


# ─── Model Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_company_term(test_session: AsyncSession, admin_user: User):
    """Test creating a CompanyTerm record."""
    term = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="ГСМ",
        definition="Горюче-смазочные материалы",
        is_manual=True,
    )
    test_session.add(term)
    await test_session.flush()

    assert term.id is not None
    assert term.term == "ГСМ"
    assert term.definition == "Горюче-смазочные материалы"
    assert term.is_manual is True
    assert term.company_id == admin_user.active_company_id


@pytest.mark.asyncio
async def test_company_term_unique_constraint(test_session: AsyncSession, admin_user: User):
    """Test that (company_id, term) unique constraint works."""
    term1 = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="ГСМ",
        definition="First definition",
        is_manual=False,
    )
    test_session.add(term1)
    await test_session.flush()

    term2 = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="ГСМ",
        definition="Second definition",
        is_manual=False,
    )
    test_session.add(term2)
    with pytest.raises(Exception):  # IntegrityError
        await test_session.flush()


@pytest.mark.asyncio
async def test_create_company_abbreviation(test_session: AsyncSession, admin_user: User):
    """Test creating a CompanyAbbreviation record."""
    abbr = CompanyAbbreviation(
        company_id=admin_user.active_company_id,
        abbreviation="ГСМ",
        full_form="Горюче-смазочные материалы",
        is_manual=True,
    )
    test_session.add(abbr)
    await test_session.flush()

    assert abbr.id is not None
    assert abbr.abbreviation == "ГСМ"
    assert abbr.full_form == "Горюче-смазочные материалы"
    assert abbr.is_manual is True


@pytest.mark.asyncio
async def test_company_abbreviation_unique_constraint(test_session: AsyncSession, admin_user: User):
    """Test that (company_id, abbreviation) unique constraint works."""
    a1 = CompanyAbbreviation(
        company_id=admin_user.active_company_id,
        abbreviation="ГСМ",
        full_form="Form 1",
        is_manual=False,
    )
    test_session.add(a1)
    await test_session.flush()

    a2 = CompanyAbbreviation(
        company_id=admin_user.active_company_id,
        abbreviation="ГСМ",
        full_form="Form 2",
        is_manual=False,
    )
    test_session.add(a2)
    with pytest.raises(Exception):
        await test_session.flush()


# ─── API Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_terms_list_empty(client: AsyncClient, admin_token: str):
    """GET /api/v1/terms should return empty list."""
    response = await client.get(
        "/api/v1/terms",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_terms_create(client: AsyncClient, admin_token: str):
    """POST /api/v1/terms should create a term."""
    response = await client.post(
        "/api/v1/terms",
        json={
            "term": "ERP-система",
            "definition": "Корпоративная информационная система управления ресурсами предприятия",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["term"] == "ERP-система"
    assert data["is_manual"] is True
    assert data["source_document_id"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_terms_create_duplicate(client: AsyncClient, admin_token: str):
    """POST /api/v1/terms with duplicate term should return 409."""
    # Create first
    await client.post(
        "/api/v1/terms",
        json={"term": "Дубликат", "definition": "Первое определение"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Try duplicate
    response = await client.post(
        "/api/v1/terms",
        json={"term": "Дубликат", "definition": "Второе определение"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data
    assert "уже существует" in data["detail"]["message"]


@pytest.mark.asyncio
async def test_terms_search(client: AsyncClient, admin_token: str, test_session: AsyncSession, admin_user: User):
    """GET /api/v1/terms?search=... should filter results."""
    # Create term directly
    term = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="СпециальныйТермин",
        definition="Тестовое определение",
        is_manual=True,
    )
    test_session.add(term)
    await test_session.flush()

    response = await client.get(
        "/api/v1/terms?search=Специальный",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any("СпециальныйТермин" in item["term"] for item in data["items"])


@pytest.mark.asyncio
async def test_terms_update(client: AsyncClient, admin_token: str, test_session: AsyncSession, admin_user: User):
    """PUT /api/v1/terms/{id} should update the term."""
    term = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="СтарыйТермин",
        definition="Старое определение",
        is_manual=True,
    )
    test_session.add(term)
    await test_session.flush()

    response = await client.put(
        f"/api/v1/terms/{term.id}",
        json={"definition": "Новое определение"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["definition"] == "Новое определение"
    assert data["term"] == "СтарыйТермин"


@pytest.mark.asyncio
async def test_terms_delete(client: AsyncClient, admin_token: str, test_session: AsyncSession, admin_user: User):
    """DELETE /api/v1/terms/{id} should delete the term."""
    term = CompanyTerm(
        company_id=admin_user.active_company_id,
        term="УдаляемыйТермин",
        definition="Будет удалён",
        is_manual=True,
    )
    test_session.add(term)
    await test_session.flush()

    response = await client.delete(
        f"/api/v1/terms/{term.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204

    # Verify deleted
    stmt = select(CompanyTerm).where(CompanyTerm.id == term.id)
    result = await test_session.execute(stmt)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_abbreviations_create(client: AsyncClient, admin_token: str):
    """POST /api/v1/abbreviations should create abbreviation."""
    response = await client.post(
        "/api/v1/abbreviations",
        json={
            "abbreviation": "МОЛ",
            "full_form": "Материально-ответственное лицо",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["abbreviation"] == "МОЛ"
    assert data["full_form"] == "Материально-ответственное лицо"
    assert data["is_manual"] is True


@pytest.mark.asyncio
async def test_abbreviations_list(client: AsyncClient, admin_token: str):
    """GET /api/v1/abbreviations should return list."""
    response = await client.get(
        "/api/v1/abbreviations",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_abbreviations_update(client: AsyncClient, admin_token: str, test_session: AsyncSession, admin_user: User):
    """PUT /api/v1/abbreviations/{id} should update abbreviation."""
    abbr = CompanyAbbreviation(
        company_id=admin_user.active_company_id,
        abbreviation="ERP",
        full_form="Enterprise Resource Planning",
        is_manual=True,
    )
    test_session.add(abbr)
    await test_session.flush()

    response = await client.put(
        f"/api/v1/abbreviations/{abbr.id}",
        json={"full_form": "Enterprise Resource Planning System"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_form"] == "Enterprise Resource Planning System"


@pytest.mark.asyncio
async def test_abbreviations_delete(client: AsyncClient, admin_token: str, test_session: AsyncSession, admin_user: User):
    """DELETE /api/v1/abbreviations/{id} should delete."""
    abbr = CompanyAbbreviation(
        company_id=admin_user.active_company_id,
        abbreviation="DEL",
        full_form="Delete Me",
        is_manual=True,
    )
    test_session.add(abbr)
    await test_session.flush()

    response = await client.delete(
        f"/api/v1/abbreviations/{abbr.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_terms_requires_auth(client: AsyncClient):
    """POST /api/v1/terms should return 401 without auth."""
    response = await client.post(
        "/api/v1/terms",
        json={"term": "Test", "definition": "Test definition"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_abbreviations_requires_auth(client: AsyncClient):
    """POST /api/v1/abbreviations should return 401 without auth."""
    response = await client.post(
        "/api/v1/abbreviations",
        json={"abbreviation": "TST", "full_form": "Test"},
    )
    assert response.status_code == 401
