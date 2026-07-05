"""

API маршруты для работы с профилями компании.



Endpoints:

- POST /api/company-profiles/upload    — загрузка 1-3 .docx файлов

- POST /api/company-profiles/{profile_id}/analyze — запуск фонового анализа

- GET  /api/company-profiles/{profile_id}         — детали профиля

- GET  /api/company-profiles/{profile_id}/paragraphs — параграфы профиля

- GET  /api/company-profiles            — список профилей

- DELETE /api/company-profiles/{profile_id} — удаление профиля

- GET  /api/company-profiles/{profile_id}/download/{doc_id} — скачать .docx

"""



import json

import logging

import os

import shutil

from dataclasses import asdict

from datetime import datetime

from typing import List, Optional



from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from fastapi.responses import FileResponse

from sqlalchemy.orm import Session

from sqlalchemy import desc



from app.database import get_db, SessionLocal

from app.models.company_profile import CompanyProfile

from app.models.uploaded_document import UploadedDocument

from app.models.analyzed_paragraph import AnalyzedParagraph as AnalyzedParagraphModel

from app.schemas.company_profile import (

    CompanyProfileCreate,

    CompanyProfileResponse,

    CompanyProfileListItem,

    CompanyProfileListResponse,

    AnalyzedParagraphResponse,

    AnalyzedParagraphListResponse,

)

from app.services.company_profile_service import (

    create_profile,

    get_profile,

    list_profiles,

    delete_profile,

    update_profile_status,

)

from app.services.paragraph_extractor import extract_paragraphs, ExtractedParagraph

from app.services.paragraph_analyzer import analyze_paragraphs, AnalysisResult

from app.services.profile_synthesizer import synthesize_profile

from app.services.pipeline_memory import store_pipeline_result

from app.config import settings
from app.providers.ollama import OllamaProvider



logger = logging.getLogger(__name__)



router = APIRouter()



# Директория для загрузок

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPLOADS_DIR = os.path.join(BASE_DIR, "uploads", "profiles")

os.makedirs(UPLOADS_DIR, exist_ok=True)



ALLOWED_EXTENSIONS = {".docx"}

MAX_FILES = 20





# ──────────────────────────────────────────────

# Helpers

# ──────────────────────────────────────────────





def _validate_docx(file: UploadFile) -> None:

    """Проверяет, что файл имеет расширение .docx."""

    if not file.filename:

        raise HTTPException(status_code=400, detail="File has no filename")

    ext = os.path.splitext(file.filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:

        raise HTTPException(

            status_code=400,

            detail=f"File '{file.filename}' is not a .docx file. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",

        )





def _paragraph_to_response(ap: AnalyzedParagraphModel) -> dict:

    """Преобразует DB модель AnalyzedParagraph в dict для ответа."""

    steps = []

    if ap.steps_json:

        try:

            steps = json.loads(ap.steps_json)

        except (json.JSONDecodeError, TypeError):

            steps = []

    return {

        "id": ap.id,

        "paragraph_index": ap.paragraph_index,

        "section_title": ap.section_title,

        "original_text": ap.original_text,

        "char_count": ap.char_count,

        "is_table_row": ap.is_table_row,

        "is_list_item": ap.is_list_item,

        "steps": steps,

    }





# ──────────────────────────────────────────────

# Background analysis task

# ──────────────────────────────────────────────





async def _run_analysis(profile_id: str) -> None:

    """

    Фоновая задача анализа профиля.



    Этапы:

    1. Extract — извлечение параграфов из .docx

    2. Analyze — LLM-анализ параграфов → Step[]

    3. Synthesize — синтез ParagraphLogicProfile

    """

    db = SessionLocal()

    try:

        # Загружаем профиль

        profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

        if not profile:

            logger.error("Profile %s not found for analysis", profile_id)

            return



        # ── Phase 1: Extract ──

        logger.info("Analysis phase 1: extracting paragraphs for profile %s", profile_id)

        profile.status = "extracting"

        profile.progress_pct = 5

        profile.updated_at = datetime.utcnow()

        db.commit()



        all_extracted: list[tuple[UploadedDocument, list[ExtractedParagraph]]] = []



        for doc in profile.documents:

            if not os.path.isfile(doc.stored_path):

                logger.warning("File not found for doc %s: %s", doc.id, doc.stored_path)

                continue



            try:

                paragraphs = extract_paragraphs(doc.stored_path)

            except Exception as e:

                logger.error("Extraction failed for doc %s: %s", doc.id, e)

                doc.status = "failed"

                doc.analysis_error = str(e)

                db.commit()

                continue



            # Сохраняем извлечённые параграфы в БД

            for p in paragraphs:

                ap = AnalyzedParagraphModel(

                    profile_id=profile_id,

                    document_id=doc.id,

                    paragraph_index=p.index,

                    section_title=p.section_title,

                    original_text=p.text,

                    steps_json="[]",

                    char_count=p.char_count,

                    is_table_row=1 if p.is_table_row else 0,

                    is_list_item=1 if p.is_list_item else 0,

                )

                db.add(ap)



            doc.status = "extracted"

            doc.paragraph_count = len(paragraphs)

            db.commit()



            all_extracted.append((doc, paragraphs))



        if not all_extracted:

            raise ValueError("No documents were successfully extracted")



        profile.progress_pct = 30

        profile.updated_at = datetime.utcnow()

        db.commit()

        logger.info("Extraction complete: %d documents", len(all_extracted))



        # ── Phase 2: Analyze with LLM (per-batch progress) ──

        logger.info("Analysis phase 2: analyzing paragraphs for profile %s", profile_id)

        profile.status = "analyzing"

        profile.progress_pct = 35

        profile.updated_at = datetime.utcnow()

        db.commit()



        # Собираем все body-параграфы (не заголовки) для анализа

        all_body_paragraphs = []

        for _doc, paragraphs in all_extracted:

            for p in paragraphs:

                if not p.is_heading:

                    all_body_paragraphs.append(p)



        if not all_body_paragraphs:

            logger.warning("No body paragraphs to analyze")

            analysis_result = AnalysisResult(paragraphs=[], stats={

                "total_paragraphs": 0,

                "total_steps": 0,

                "paragraphs_with_role_pct": 0.0,

                "paragraphs_with_deadline_pct": 0.0,

                "paragraphs_with_method_pct": 0.0,

                "paragraphs_with_condition_pct": 0.0,

                "paragraphs_with_document_pct": 0.0,

                "paragraphs_with_consequence_pct": 0.0,

                "avg_steps_per_paragraph": 0.0,

                "parse_error_count": 0,

            })

        else:
            try:
                provider = OllamaProvider(
                    model=settings.ollama_model,
                    base_url=settings.ollama_base_url,
                )
            except Exception as e:
                logger.error("Failed to initialize LLM provider for profile %s: %s", profile_id, e)
                profile.status = "failed"
                profile.error_message = f"Provider initialization failed: {str(e)[:500]}"
                profile.updated_at = datetime.utcnow()
                db.commit()
                return

            # Callback: save batch results and update progress after each batch
            total_para = len(all_body_paragraphs)
            processed_count = 0

            async def on_batch_complete(batch_num: int, total_batches: int, batch_results: list):
                """Save batch results to DB and update progress after each batch."""
                nonlocal processed_count
                processed_count += len(batch_results)

                # Update existing DB records with analyzed steps
                for ap in batch_results:
                    db_ap = (
                        db.query(AnalyzedParagraphModel)
                        .filter(
                            AnalyzedParagraphModel.profile_id == profile_id,
                            AnalyzedParagraphModel.paragraph_index == ap.paragraph_index,
                        )
                        .first()
                    )
                    if db_ap and ap.steps:
                        steps_dicts = []
                        for s in ap.steps:
                            d = {}
                            if s.role:
                                d["role"] = s.role
                            if s.action:
                                d["action"] = s.action
                            if s.deadline:
                                d["deadline"] = s.deadline
                            if s.method:
                                d["method"] = s.method
                            if s.condition:
                                d["condition"] = s.condition
                            if s.document:
                                d["document"] = s.document
                            if s.consequence:
                                d["consequence"] = s.consequence
                            steps_dicts.append(d)
                        db_ap.steps_json = json.dumps(steps_dicts, ensure_ascii=False)
                db.commit()

                # Calculate progress within Phase B (35% to 60%)
                phase_start_pct = 35
                phase_end_pct = 60
                current_pct = phase_start_pct + int((phase_end_pct - phase_start_pct) * batch_num / total_batches)

                # Update profile progress
                profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()
                if profile:
                    profile.progress_pct = current_pct
                    profile.analysis_stats = json.dumps({
                        "phase": "analyzing",
                        "batch": batch_num,
                        "total_batches": total_batches,
                        "paragraphs_processed": processed_count,
                        "total_paragraphs": total_para,
                        "last_batch_at": datetime.utcnow().isoformat() + "Z",
                    }, ensure_ascii=False)
                    profile.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(
                        "Progress: %d%% - batch %d/%d (%d/%d paragraphs)",
                        current_pct, batch_num, total_batches,
                        processed_count, total_para,
                    )

            analysis_result = await analyze_paragraphs(
                all_body_paragraphs,
                provider,
                on_batch_complete=on_batch_complete,
            )
            logger.info(
                "Analysis complete: %d paragraphs, %d steps",
                analysis_result.stats.get("total_paragraphs", 0),
                analysis_result.stats.get("total_steps", 0),
            )


        profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

        if profile:
            profile.progress_pct = 65

            profile.updated_at = datetime.utcnow()

            db.commit()




        # ── Phase 3: Synthesize profile ──

        logger.info("Analysis phase 3: synthesizing profile for %s", profile_id)

        profile.status = "synthesizing"

        profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

        if not profile:
            logger.error("Profile %s not found for Phase 3", profile_id)
            return

        profile.progress_pct = 70

        profile.analysis_stats = json.dumps({"phase": "synthesizing", "detail": "Building step templates..."}, ensure_ascii=False)

        profile.updated_at = datetime.utcnow()

        db.commit()



        # Собираем все шаги для синтеза

        all_steps_for_synthesis = [

            (ap.paragraph_index, ap) for ap in analysis_result.paragraphs

        ]



        if not all_steps_for_synthesis:

            logger.warning("No steps for synthesis, using empty profile")

            profile_data = None

        else:

            try:

                provider = OllamaProvider(

                    model=settings.ollama_model,

                    base_url=settings.ollama_base_url,

                )

            except Exception as e:

                logger.error("Failed to initialize LLM provider for synthesis (profile %s): %s", profile_id, e)

                profile.status = "failed"

                profile.error_message = f"Provider initialization failed: {str(e)[:500]}"

                profile.updated_at = datetime.utcnow()

                db.commit()

                return

            profile_data = await synthesize_profile(

                all_steps_for_synthesis,

                provider,

                document_count=len(all_extracted),

            )

            profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

            if profile:
                profile.progress_pct = 85

                profile.analysis_stats = json.dumps({"phase": "synthesizing", "detail": "Extracting vocabulary and rules..."}, ensure_ascii=False)

                profile.updated_at = datetime.utcnow()

                db.commit()

        # Сохраняем профиль

        if profile_data is not None:

            profile.profile_json = json.dumps(asdict(profile_data), ensure_ascii=False, default=str)

        else:

            profile.profile_json = json.dumps({

                "version": 2,

                "source_document_count": len(all_extracted),

                "total_steps_analyzed": 0,

                "step_templates": [],

                "vocabulary": {},

                "logic_rules": {},

                "section_patterns": {},

                "transition_patterns": [],

            }, ensure_ascii=False)



        final_stats = dict(analysis_result.stats)
        final_stats["phase"] = "complete"
        profile.analysis_stats = json.dumps(final_stats, ensure_ascii=False, default=str)

        profile.document_count = len(all_extracted)

        profile.status = "ready"

        profile.progress_pct = 100

        profile.updated_at = datetime.utcnow()

        db.commit()

        logger.info("Profile %s analysis complete", profile_id)

        # ── Store pipeline result in MCP Memory ──
        if profile_data is not None:
            try:
                profile_as_dict = asdict(profile_data)
                memory_ok = await store_pipeline_result(
                    profile_id=profile_id,
                    stats=final_stats,
                    profile_dict=profile_as_dict,
                    document_count=len(all_extracted),
                )
                if memory_ok.get("analysis_stored") or memory_ok.get("profile_stored"):
                    logger.info("Pipeline result stored in MCP Memory for profile %s", profile_id)
                else:
                    logger.info("MCP Memory not available (non-critical)")
            except Exception as mem_err:
                logger.warning("MCP Memory store skipped (non-critical): %s", mem_err)



    except Exception as e:

        logger.error("Analysis failed for profile %s: %s", profile_id, e)

        try:

            profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

            if profile:

                profile.status = "failed"

                profile.error_message = str(e)[:1000]

                profile.updated_at = datetime.utcnow()

                db.commit()

        except Exception:

            pass

    finally:

        db.close()





# ──────────────────────────────────────────────

# Endpoints

# ──────────────────────────────────────────────





@router.post(

    "/api/company-profiles/upload",

    status_code=201,

)

async def upload_company_profile(

    name: str = Form(..., description="Название профиля (1–200 символов)"),

    description: str = Form("", description="Описание профиля"),

    files: List[UploadFile] = File(..., description="DOCX-файлы (1–3 шт)"),

    db: Session = Depends(get_db),

):

    """Загрузить 1–3 .docx файла и создать профиль компании."""

    # Валидация количества файлов

    if not files:

        raise HTTPException(status_code=400, detail="At least one file is required")

    if len(files) > MAX_FILES:

        raise HTTPException(

            status_code=400,

            detail=f"Maximum {MAX_FILES} files allowed, got {len(files)}",

        )



    # Валидация расширений

    for f in files:

        _validate_docx(f)



    # Создаём профиль

    profile = await create_profile(db, name=name, description=description)



    # Создаём директорию для файлов

    profile_dir = os.path.join(UPLOADS_DIR, profile.id)

    os.makedirs(profile_dir, exist_ok=True)



    # Сохраняем файлы

    saved_docs = []

    for file in files:

        file_path = os.path.join(profile_dir, file.filename)

        content = await file.read()

        with open(file_path, "wb") as f:

            f.write(content)



        # Создаём запись UploadedDocument

        doc = UploadedDocument(

            profile_id=profile.id,

            original_name=file.filename,

            stored_path=file_path,

            file_size=len(content),

            status="uploaded",

        )

        db.add(doc)

        saved_docs.append(doc)



    # Update document_count on the profile
    profile.document_count = len(saved_docs)
    db.commit()
    db.refresh(profile)

    logger.info(
        "Profile created: id=%s name=%s files=%d",
        profile.id,
        name,
        len(saved_docs),
    )


    return {

        "profile_id": profile.id,

        "name": profile.name,

        "status": profile.status,

        "document_count": len(saved_docs),

        "documents": [

            {

                "id": doc.id,

                "original_name": doc.original_name,

                "file_size": doc.file_size,

                "status": doc.status,

            }

            for doc in saved_docs

        ],

    }





@router.post(

    "/api/company-profiles/{profile_id}/analyze",

    status_code=202,

)

async def start_profile_analysis(

    profile_id: str,

    db: Session = Depends(get_db),

):

    """Запустить фоновый анализ профиля: extract → analyze → synthesize."""

    profile = await get_profile(db, profile_id)

    if not profile:

        raise HTTPException(status_code=404, detail="Profile not found")



    if profile.status not in ("uploaded", "failed"):

        raise HTTPException(

            status_code=400,

            detail=f"Cannot analyze profile in status '{profile.status}'. Expected 'uploaded' or 'failed'.",

        )



    # Сбрасываем статус

    profile.status = "extracting"

    profile.progress_pct = 0

    profile.error_message = None

    profile.updated_at = datetime.utcnow()

    db.commit()



    # Запускаем фоновую задачу

    import asyncio

    asyncio.create_task(_run_analysis(profile_id))



    return {

        "profile_id": profile_id,

        "status": "extracting",

        "estimated_seconds": 120,

        "message": "Analysis started. Use GET /api/company-profiles/{profile_id} to track progress.",

    }





@router.get(

    "/api/company-profiles/{profile_id}",

    response_model=CompanyProfileResponse,

)

async def get_company_profile(

    profile_id: str,

    db: Session = Depends(get_db),

):

    """Получить детальную информацию о профиле."""

    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

    if not profile:

        raise HTTPException(status_code=404, detail="Profile not found")

    # Загружаем документы

    docs = (
        db.query(UploadedDocument)
        .filter(UploadedDocument.profile_id == profile_id)
        .all()
    )

    # Корректируем document_count: если в БД 0, но документы есть — считаем из отношения
    doc_count = len(docs) if docs else profile.document_count

    return CompanyProfileResponse(
        id=profile.id,
        name=profile.name,
        description=profile.description or "",
        profile_type=profile.profile_type,
        document_count=doc_count,
        status=profile.status,

        progress_pct=profile.progress_pct,

        profile_json=profile.profile_json,

        analysis_stats=profile.analysis_stats,

        documents=[

            {

                "id": doc.id,

                "original_name": doc.original_name,

                "file_size": doc.file_size,

                "status": doc.status,

                "paragraph_count": doc.paragraph_count,

                "step_count": doc.step_count,

                "created_at": doc.created_at.isoformat() if doc.created_at else None,

            }

            for doc in docs

        ],

        created_at=profile.created_at,

        updated_at=profile.updated_at,

    )





@router.get(

    "/api/company-profiles/{profile_id}/paragraphs",

    response_model=AnalyzedParagraphListResponse,

)

async def get_profile_paragraphs(

    profile_id: str,

    document_id: Optional[str] = Query(None, description="Фильтр по ID документа"),

    limit: int = Query(default=50, ge=1, le=500),

    offset: int = Query(default=0, ge=0),

    db: Session = Depends(get_db),

):

    """Получить список проанализированных параграфов профиля."""

    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

    if not profile:

        raise HTTPException(status_code=404, detail="Profile not found")



    query = db.query(AnalyzedParagraphModel).filter(

        AnalyzedParagraphModel.profile_id == profile_id

    )



    if document_id:

        query = query.filter(AnalyzedParagraphModel.document_id == document_id)



    total = query.count()



    items = (

        query.order_by(AnalyzedParagraphModel.paragraph_index)

        .offset(offset)

        .limit(limit)

        .all()

    )



    return AnalyzedParagraphListResponse(

        items=[_paragraph_to_response(ap) for ap in items],

        total=total,

    )





@router.get(

    "/api/company-profiles",

    response_model=CompanyProfileListResponse,

)

async def list_company_profiles(

    status: Optional[str] = Query(None, description="Фильтр по статусу"),

    profile_type: Optional[str] = Query(None, description="Фильтр по типу профиля"),

    limit: int = Query(default=20, ge=1, le=100),

    offset: int = Query(default=0, ge=0),

    db: Session = Depends(get_db),

):

    """Получить список профилей компании."""

    profiles, total = await list_profiles(

        db,

        status=status,

        profile_type=profile_type,

        limit=limit,

        offset=offset,

    )



    return CompanyProfileListResponse(

        items=[

            CompanyProfileListItem(

                id=p.id,

                name=p.name,

                document_count=p.document_count,

                status=p.status,

                progress_pct=p.progress_pct,

                analysis_stats=p.analysis_stats,

                created_at=p.created_at,

            )

            for p in profiles

        ],

        total=total,

    )





@router.delete(

    "/api/company-profiles/{profile_id}",

    status_code=200,

)

async def delete_company_profile(

    profile_id: str,

    db: Session = Depends(get_db),

):

    """Удалить профиль и все связанные данные."""

    profile = db.query(CompanyProfile).filter(CompanyProfile.id == profile_id).first()

    if not profile:

        raise HTTPException(status_code=404, detail="Profile not found")



    # Удаляем файлы на диске

    profile_dir = os.path.join(UPLOADS_DIR, profile_id)

    if os.path.isdir(profile_dir):

        shutil.rmtree(profile_dir)

        logger.info("Deleted profile directory: %s", profile_dir)



    # Удаляем из БД (каскадно удалит документы и параграфы)

    deleted = await delete_profile(db, profile_id)



    return {

        "deleted": deleted,

        "profile_id": profile_id,

    }





@router.get(

    "/api/company-profiles/{profile_id}/download/{doc_id}",

)

async def download_uploaded_document(

    profile_id: str,

    doc_id: str,

    db: Session = Depends(get_db),

):

    """Скачать оригинальный загруженный .docx файл."""

    doc = (

        db.query(UploadedDocument)

        .filter(

            UploadedDocument.id == doc_id,

            UploadedDocument.profile_id == profile_id,

        )

        .first()

    )

    if not doc:

        raise HTTPException(status_code=404, detail="Document not found")



    if not os.path.isfile(doc.stored_path):

        raise HTTPException(status_code=404, detail="File not found on disk")



    return FileResponse(

        path=doc.stored_path,

        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",

        filename=doc.original_name,

    )

