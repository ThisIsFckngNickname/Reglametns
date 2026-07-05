"""
document_analysis_routes — API endpoints для загрузки и анализа документов.

Flow:
  POST /api/documents/upload  → Upload .docx → получаем DocumentAnalysis
  POST /api/documents/{id}/analyze → Запуск анализа (extract → analyze → insights)
  GET  /api/documents/{id}     → Получить статус и результаты
  GET  /api/documents          → Список всех анализов
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document_analysis import DocumentAnalysis
from app.services.document_upload_service import upload_document, run_analysis_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["Document Analysis"])


# ── Pydantic schemas ──────────────────────────────────────


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    file_size: int
    status: str
    total_paragraphs: int
    total_steps: int
    insights: Optional[dict] = None
    stats: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str

    @classmethod
    def from_db(cls, doc: DocumentAnalysis) -> "DocumentResponse":
        return cls(
            id=doc.id,
            original_filename=doc.original_filename,
            file_size=doc.file_size,
            status=doc.status,
            total_paragraphs=doc.total_paragraphs,
            total_steps=doc.total_steps,
            insights=json.loads(doc.insights_json) if doc.insights_json else None,
            stats=json.loads(doc.analysis_stats) if doc.analysis_stats else None,
            error_message=doc.error_message,
            created_at=doc.created_at.isoformat() if isinstance(doc.created_at, datetime) else str(doc.created_at),
            updated_at=doc.updated_at.isoformat() if isinstance(doc.updated_at, datetime) else str(doc.updated_at),
        )


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class AnalyzeResponse(BaseModel):
    id: str
    status: str
    message: str


class UploadResponse(BaseModel):
    id: str
    original_filename: str
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────


@router.post("/upload", response_model=UploadResponse)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Загрузка .docx файла для анализа.

    - Проверяет расширение файла (.docx)
    - Сохраняет файл в /data/uploads/
    - Создаёт запись DocumentAnalysis
    - Возвращает ID для дальнейшего анализа
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Только .docx файлы поддерживаются")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Пустой файл")

    try:
        doc = upload_document(file.filename, content, db)
    except Exception as e:
        logger.error("Upload failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return UploadResponse(
        id=doc.id,
        original_filename=doc.original_filename,
        status=doc.status,
        message="Файл загружен. Используйте POST /api/documents/{id}/analyze для запуска анализа.",
    )


@router.post("/{id}/analyze", response_model=AnalyzeResponse)
async def analyze_document(
    id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Запуск анализа документа.

    Выполняет пайплайн:
    1. Извлечение параграфов из .docx
    2. LLM-анализ каждого параграфа
    3. Синтез инсайтов (шаблоны, словарь, правила)

    Возвращает 202 Accepted — анализ выполняется асинхронно.
    Статус можно отслеживать через GET /api/documents/{id}
    """
    doc = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")

    if doc.status != "uploaded":
        raise HTTPException(
            status_code=400,
            detail=f"Некорректный статус: {doc.status}. Ожидается 'uploaded'.",
        )

    # Получаем провайдера из селектора
    selector = request.app.state.selector
    provider = await selector.select(topic="document_analysis", preference="auto")

    # Запускаем фоновый анализ
    async def _run():
        try:
            await run_analysis_pipeline(id, provider, db)
        except Exception as e:
            logger.error("Background analysis failed for %s: %s", id, e)

    background_tasks.add_task(_run)

    return AnalyzeResponse(
        id=id,
        status="analyzing",
        message="Анализ запущен в фоне. Используйте GET /api/documents/{id} для отслеживания статуса.",
    )


@router.get("/{id}", response_model=DocumentResponse)
async def get_document_analysis(
    id: str,
    db: Session = Depends(get_db),
):
    """Получить статус и результаты анализа документа."""
    doc = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден")
    return DocumentResponse.from_db(doc)


@router.get("", response_model=DocumentListResponse)
async def list_document_analyses(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Список всех загруженных документов с результатами анализа."""
    total = db.query(DocumentAnalysis).count()
    docs = (
        db.query(DocumentAnalysis)
        .order_by(DocumentAnalysis.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return DocumentListResponse(
        documents=[DocumentResponse.from_db(d) for d in docs],
        total=total,
    )
