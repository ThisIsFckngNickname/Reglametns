"""
API router for CompanyTerm and CompanyAbbreviation CRUD.

Provides 8 endpoints for managing holding-wide terms and abbreviations:
- GET/POST/PUT/DELETE /api/v1/terms
- GET/POST/PUT/DELETE /api/v1/abbreviations
"""

import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_active_company, require_editor
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.database import get_db
from app.models.company_term import CompanyTerm
from app.models.company_abbreviation import CompanyAbbreviation
from app.models.document import Document
from app.models.user import User
from app.schemas.company_term import (
    CompanyTermCreate,
    CompanyTermUpdate,
    CompanyTermResponse,
    CompanyTermListResponse,
    CompanyAbbreviationCreate,
    CompanyAbbreviationUpdate,
    CompanyAbbreviationResponse,
    CompanyAbbreviationListResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["company-terms"])


# ─── Helpers ─────────────────────────────────────────────────────────────

async def _resolve_source_document_title(
    source_document_id: Optional[int],
    db: AsyncSession,
) -> Optional[str]:
    """Resolve source document title by ID."""
    if source_document_id is None:
        return None
    stmt = select(Document.title).where(Document.id == source_document_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    return row if row else None


def _build_term_response(term: CompanyTerm, doc_title: Optional[str] = None) -> CompanyTermResponse:
    return CompanyTermResponse(
        id=term.id,
        company_id=term.company_id,
        term=term.term,
        definition=term.definition,
        source_document_id=term.source_document_id,
        source_document_title=doc_title,
        is_manual=term.is_manual,
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


def _build_abbreviation_response(
    abbr: CompanyAbbreviation, doc_title: Optional[str] = None
) -> CompanyAbbreviationResponse:
    return CompanyAbbreviationResponse(
        id=abbr.id,
        company_id=abbr.company_id,
        abbreviation=abbr.abbreviation,
        full_form=abbr.full_form,
        source_document_id=abbr.source_document_id,
        source_document_title=doc_title,
        is_manual=abbr.is_manual,
        created_at=abbr.created_at,
        updated_at=abbr.updated_at,
    )


# ─── Terms CRUD ──────────────────────────────────────────────────────────

@router.get("/terms", response_model=CompanyTermListResponse)
async def list_terms(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """List company terms with pagination and optional search."""
    company_id = user.active_company_id
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    # Build query
    base_query = select(CompanyTerm).where(CompanyTerm.company_id == company_id)
    count_query = select(func.count(CompanyTerm.id)).where(CompanyTerm.company_id == company_id)

    if search:
        search_filter = CompanyTerm.term.ilike(f"%{search}%")
        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    # Get items
    stmt = base_query.order_by(CompanyTerm.term.asc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    terms = result.scalars().all()

    # Resolve source document titles
    items = []
    for term in terms:
        doc_title = await _resolve_source_document_title(term.source_document_id, db)
        items.append(_build_term_response(term, doc_title))

    return CompanyTermListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/terms", response_model=CompanyTermResponse, status_code=201)
async def create_term(
    request: CompanyTermCreate,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Create a new company term (editor+ required)."""
    company_id = user.active_company_id

    # Check for duplicate
    stmt = select(CompanyTerm).where(
        CompanyTerm.company_id == company_id,
        CompanyTerm.term == request.term,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictException(
            message=f"Термин '{request.term}' уже существует в данном холдинге",
            field="term",
        )

    term = CompanyTerm(
        company_id=company_id,
        term=request.term,
        definition=request.definition,
        is_manual=True,
    )
    db.add(term)
    await db.flush()
    await db.refresh(term)

    doc_title = await _resolve_source_document_title(term.source_document_id, db)
    return _build_term_response(term, doc_title)


@router.put("/terms/{term_id}", response_model=CompanyTermResponse)
async def update_term(
    term_id: int,
    request: CompanyTermUpdate,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Update a company term (editor+ required)."""
    company_id = user.active_company_id

    # Load term
    stmt = select(CompanyTerm).where(CompanyTerm.id == term_id)
    result = await db.execute(stmt)
    term = result.scalar_one_or_none()
    if not term:
        raise NotFoundException(message="Термин не найден", field="id")

    # Check company isolation
    if term.company_id != company_id:
        raise ForbiddenException(message="Чужой термин холдинга", field="id")

    # Check for duplicate term name if changing term
    if request.term is not None and request.term != term.term:
        dup_stmt = select(CompanyTerm).where(
            CompanyTerm.company_id == company_id,
            CompanyTerm.term == request.term,
            CompanyTerm.id != term_id,
        )
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
            raise ConflictException(
                message=f"Термин '{request.term}' уже существует в данном холдинге",
                field="term",
            )
        term.term = request.term

    if request.definition is not None:
        term.definition = request.definition

    await db.flush()
    await db.refresh(term)

    doc_title = await _resolve_source_document_title(term.source_document_id, db)
    return _build_term_response(term, doc_title)


@router.delete("/terms/{term_id}", status_code=204)
async def delete_term(
    term_id: int,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Delete a company term (editor+ required)."""
    company_id = user.active_company_id

    stmt = select(CompanyTerm).where(CompanyTerm.id == term_id)
    result = await db.execute(stmt)
    term = result.scalar_one_or_none()
    if not term:
        raise NotFoundException(message="Термин не найден", field="id")

    if term.company_id != company_id:
        raise ForbiddenException(message="Чужой термин холдинга", field="id")

    await db.delete(term)
    await db.flush()


# ─── Abbreviations CRUD ──────────────────────────────────────────────────

@router.get("/abbreviations", response_model=CompanyAbbreviationListResponse)
async def list_abbreviations(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(require_active_company),
    db: AsyncSession = Depends(get_db),
):
    """List company abbreviations with pagination and optional search."""
    company_id = user.active_company_id
    page = max(1, page)
    page_size = max(1, min(100, page_size))
    offset = (page - 1) * page_size

    base_query = select(CompanyAbbreviation).where(
        CompanyAbbreviation.company_id == company_id
    )
    count_query = select(func.count(CompanyAbbreviation.id)).where(
        CompanyAbbreviation.company_id == company_id
    )

    if search:
        search_filter = CompanyAbbreviation.abbreviation.ilike(f"%{search}%")
        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    pages = max(1, math.ceil(total / page_size))

    stmt = base_query.order_by(CompanyAbbreviation.abbreviation.asc()).offset(offset).limit(page_size)
    result = await db.execute(stmt)
    abbreviations = result.scalars().all()

    items = []
    for abbr in abbreviations:
        doc_title = await _resolve_source_document_title(abbr.source_document_id, db)
        items.append(_build_abbreviation_response(abbr, doc_title))

    return CompanyAbbreviationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/abbreviations", response_model=CompanyAbbreviationResponse, status_code=201)
async def create_abbreviation(
    request: CompanyAbbreviationCreate,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Create a new company abbreviation (editor+ required)."""
    company_id = user.active_company_id

    # Check for duplicate
    stmt = select(CompanyAbbreviation).where(
        CompanyAbbreviation.company_id == company_id,
        CompanyAbbreviation.abbreviation == request.abbreviation,
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        raise ConflictException(
            message=f"Сокращение '{request.abbreviation}' уже существует в данном холдинге",
            field="abbreviation",
        )

    abbr = CompanyAbbreviation(
        company_id=company_id,
        abbreviation=request.abbreviation,
        full_form=request.full_form,
        is_manual=True,
    )
    db.add(abbr)
    await db.flush()
    await db.refresh(abbr)

    doc_title = await _resolve_source_document_title(abbr.source_document_id, db)
    return _build_abbreviation_response(abbr, doc_title)


@router.put("/abbreviations/{abbr_id}", response_model=CompanyAbbreviationResponse)
async def update_abbreviation(
    abbr_id: int,
    request: CompanyAbbreviationUpdate,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Update a company abbreviation (editor+ required)."""
    company_id = user.active_company_id

    stmt = select(CompanyAbbreviation).where(CompanyAbbreviation.id == abbr_id)
    result = await db.execute(stmt)
    abbr = result.scalar_one_or_none()
    if not abbr:
        raise NotFoundException(message="Сокращение не найдено", field="id")

    if abbr.company_id != company_id:
        raise ForbiddenException(message="Чужое сокращение холдинга", field="id")

    # Check for duplicate abbreviation if changing
    if request.abbreviation is not None and request.abbreviation != abbr.abbreviation:
        dup_stmt = select(CompanyAbbreviation).where(
            CompanyAbbreviation.company_id == company_id,
            CompanyAbbreviation.abbreviation == request.abbreviation,
            CompanyAbbreviation.id != abbr_id,
        )
        dup_result = await db.execute(dup_stmt)
        if dup_result.scalar_one_or_none():
            raise ConflictException(
                message=f"Сокращение '{request.abbreviation}' уже существует в данном холдинге",
                field="abbreviation",
            )
        abbr.abbreviation = request.abbreviation

    if request.full_form is not None:
        abbr.full_form = request.full_form

    await db.flush()
    await db.refresh(abbr)

    doc_title = await _resolve_source_document_title(abbr.source_document_id, db)
    return _build_abbreviation_response(abbr, doc_title)


@router.delete("/abbreviations/{abbr_id}", status_code=204)
async def delete_abbreviation(
    abbr_id: int,
    user: User = Depends(require_editor),
    db: AsyncSession = Depends(get_db),
):
    """Delete a company abbreviation (editor+ required)."""
    company_id = user.active_company_id

    stmt = select(CompanyAbbreviation).where(CompanyAbbreviation.id == abbr_id)
    result = await db.execute(stmt)
    abbr = result.scalar_one_or_none()
    if not abbr:
        raise NotFoundException(message="Сокращение не найдено", field="id")

    if abbr.company_id != company_id:
        raise ForbiddenException(message="Чужое сокращение холдинга", field="id")

    await db.delete(abbr)
    await db.flush()
