"""
API маршруты (endpoints).

Stage 2: все провайдеры, auto-select, fallback.
"""

import asyncio
import json
import logging
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.session import GenerationSession
from app.schemas.document import (
    GenerateRequest,
    GenerateResponse,
    DocumentResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    ProviderStatus,
    ProvidersResponse,
    ErrorResponse,
)
from app.schemas.generation import GenerationStatusResponse, GenerationStartResponse
from app.services.generator import generate_document
from app.services.docx_builder import make_filename
from app.services.multi_stage_generator import run_multi_stage_generation
from app.providers.selector import ProviderSelector


class MultiStageRequest(BaseModel):
    """Запрос на multi-stage генерацию."""

    topic: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Тема регламента (1–2000 символов)",
    )
    provider: str = Field(
        default="auto",
        description="Выбор AI-провайдера: auto, groq, ollama, yandexgpt",
    )
    document_id: Optional[str] = Field(
        default=None,
        description="ID проанализированного документа для использования инсайтов как контекста",
    )

logger = logging.getLogger(__name__)

router = APIRouter()


def get_selector(request: Request) -> ProviderSelector:
    """Получить ProviderSelector из app.state."""
    return request.app.state.selector


@router.post(
    "/api/generate",
    status_code=201,
    response_model=GenerateResponse,
)
async def api_generate(
    request: GenerateRequest,
    db: Session = Depends(get_db),
    selector: ProviderSelector = Depends(get_selector),
):
    """Сгенерировать регламент по теме."""
    logger.info("POST /api/generate: topic='%s', provider='%s'", request.topic, request.provider)

    try:
        doc = await generate_document(
            topic=request.topic,
            selector=selector,
            preference=request.provider.value,
            db=db,
        )
    except Exception as e:
        logger.error("Generation failed: %s", e)
        raise HTTPException(
            status_code=503,
            detail=f"Generation failed: {str(e)}",
        )

    if doc.status == "failed":
        raise HTTPException(
            status_code=503,
            detail=f"Generation failed: {doc.error_message}",
        )

    filename = make_filename(doc.topic)

    return GenerateResponse(
        id=doc.id,
        topic=doc.topic,
        filename=filename,
        provider_used=doc.provider_used,
        status=doc.status,
        created_at=doc.created_at,
    )


@router.post(
    "/api/generate/multi",
    status_code=202,
    response_model=GenerationStartResponse,
)
async def start_multi_stage_generation(
    request: MultiStageRequest,
    selector: ProviderSelector = Depends(get_selector),
    db: Session = Depends(get_db),
):
    """Запустить многоэтапную генерацию регламента (async)."""
    # Выбрать провайдера
    try:
        provider = await selector.select(request.topic, request.provider)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Загружаем инсайты документа, если указан document_id
    profile_context = None
    if request.document_id:
        doc_analysis = db.query(DocumentAnalysis).filter(
            DocumentAnalysis.id == request.document_id
        ).first()
        if doc_analysis and doc_analysis.insights_json and doc_analysis.status == "ready":
            insights = json.loads(doc_analysis.insights_json)
            # Форматируем инсайты как контекст для генерации
            context_parts = ["## Контекст из проанализированного документа\n"]

            if insights.get("step_templates"):
                context_parts.append("### Шаблоны предложений")
                for tpl in insights["step_templates"][:5]:
                    context_parts.append(f"- {tpl}")
                context_parts.append("")

            if insights.get("vocabulary"):
                vocab = insights["vocabulary"]
                context_parts.append("### Словарь терминов")
                if vocab.get("roles"):
                    roles_str = ", ".join(list(vocab["roles"].keys())[:10])
                    context_parts.append(f"- Роли: {roles_str}")
                if vocab.get("actions"):
                    actions_str = ", ".join(list(vocab["actions"].keys())[:10])
                    context_parts.append(f"- Действия: {actions_str}")
                if vocab.get("conditions"):
                    context_parts.append(f"- Условия: {', '.join(vocab['conditions'][:5])}")
                if vocab.get("documents"):
                    context_parts.append(f"- Документы: {', '.join(vocab['documents'][:5])}")
                if vocab.get("methods"):
                    context_parts.append(f"- Способы: {', '.join(vocab['methods'][:5])}")
                context_parts.append("")

            if insights.get("logic_rules"):
                rules = insights["logic_rules"]
                context_parts.append("### Правила логики")
                for key, val in rules.items():
                    if isinstance(val, bool):
                        context_parts.append(f"- {key}: {'да' if val else 'нет'}")
                    elif isinstance(val, list):
                        context_parts.append(f"- {key}: {', '.join(val)}")
                context_parts.append("")

            profile_context = "\n".join(context_parts)
            logger.info("Loaded document insights for context: %s", request.document_id)
        elif doc_analysis and doc_analysis.status != "ready":
            logger.warning(
                "Document %s has status %s, skipping context",
                request.document_id,
                doc_analysis.status,
            )

    # Создать сессию
    session = GenerationSession(
        topic=request.topic,
        status="accepted",
        current_stage="accepted",
        provider_used=selector._get_provider_id(provider),
    )
    db.add(session)
    db.commit()

    # Запустить фоновую задачу (db не передаём — генератор сам создаёт сессию)
    asyncio.create_task(
        run_multi_stage_generation(
            session.id,
            provider,
            profile_context=profile_context,
        )
    )

    return GenerationStartResponse(generation_id=session.id)


@router.get(
    "/api/generate/{generation_id}/status",
    response_model=GenerationStatusResponse,
)
async def get_generation_status(generation_id: str, db: Session = Depends(get_db)):
    """Получить статус multi-stage генерации."""
    session = db.query(GenerationSession).filter(GenerationSession.id == generation_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Generation session not found")
    return GenerationStatusResponse(**session.to_dict())


@router.get(
    "/api/documents",
    response_model=DocumentListResponse,
)
def api_list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Получить историю генераций."""
    total = db.query(Document).count()
    items = (
        db.query(Document)
        .order_by(desc(Document.created_at))
        .offset(offset)
        .limit(limit)
        .all()
    )
    return DocumentListResponse(
        items=[
            DocumentResponse(
                id=doc.id,
                topic=doc.topic,
                provider_used=doc.provider_used,
                status=doc.status,
                created_at=doc.created_at,
            )
            for doc in items
        ],
        total=total,
    )


@router.get(
    "/api/documents/{doc_id}",
    response_model=DocumentDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
def api_get_document(doc_id: str, db: Session = Depends(get_db)):
    """Получить детали документа."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentDetailResponse(
        id=doc.id,
        topic=doc.topic,
        prompt=doc.prompt,
        provider_used=doc.provider_used,
        status=doc.status,
        error_message=doc.error_message,
        created_at=doc.created_at,
    )


@router.get(
    "/api/documents/{doc_id}/download",
    responses={
        200: {
            "content": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document": {}},
        },
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
def api_download_document(doc_id: str, db: Session = Depends(get_db)):
    """Скачать .docx файл."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status == "failed":
        raise HTTPException(
            status_code=400,
            detail="Document generation failed, no file available",
        )

    if not doc.docx_path or not os.path.isfile(doc.docx_path):
        raise HTTPException(
            status_code=404,
            detail="File not found on disk",
        )

    filename = make_filename(doc.topic)

    return FileResponse(
        path=doc.docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


@router.get(
    "/api/providers",
    response_model=ProvidersResponse,
)
async def api_list_providers(selector: ProviderSelector = Depends(get_selector)):
    """Получить статусы всех провайдеров."""
    # Обновляем health-check
    await selector.refresh_health()

    providers_data = selector.list_providers_with_status()

    return ProvidersResponse(
        providers=[
            ProviderStatus(
                id=p["id"],
                name=p["name"],
                available=p["available"],
                model=p["model"],
                error=p["error"],
            )
            for p in providers_data
        ]
    )
