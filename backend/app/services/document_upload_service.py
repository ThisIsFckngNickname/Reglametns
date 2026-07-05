"""
document_upload_service — сервис для загрузки .docx файлов и запуска анализа.
"""

import os
import json
import logging
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.document_analysis import DocumentAnalysis
from app.services.paragraph_extractor import extract_paragraphs
from app.services.paragraph_analyzer import analyze_paragraphs, Step, AnalyzedParagraph
from app.services.insight_generator import generate_insights, DocumentInsights
from app.services.pipeline_memory import store_pipeline_result
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "uploads")


def _ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)


def upload_document(
    filename: str,
    file_content: bytes,
    db: Session,
) -> DocumentAnalysis:
    """
    Сохраняет загруженный .docx файл и создаёт запись DocumentAnalysis.
    """
    _ensure_upload_dir()
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}_{filename}"
    stored_path = os.path.join(UPLOAD_DIR, safe_filename)

    with open(stored_path, "wb") as f:
        f.write(file_content)

    doc = DocumentAnalysis(
        id=file_id,
        original_filename=filename,
        stored_path=stored_path,
        file_size=len(file_content),
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info("Document uploaded: %s (%s, %d bytes)", doc.id, filename, len(file_content))
    return doc


async def run_analysis_pipeline(
    document_id: str,
    provider: BaseLLMProvider,
    db: Session,
) -> DocumentAnalysis:
    """
    Запускает полный пайплайн анализа документа:
    1. extract_paragraphs
    2. analyze_paragraphs
    3. generate_insights
    4. Сохраняет результаты в DocumentAnalysis
    """
    doc = db.query(DocumentAnalysis).filter(DocumentAnalysis.id == document_id).first()
    if not doc:
        raise ValueError(f"DocumentAnalysis {document_id} not found")

    if doc.status != "uploaded":
        raise ValueError(f"DocumentAnalysis {document_id} has invalid status: {doc.status}")

    try:
        # 1. Extract paragraphs
        doc.status = "extracting"
        db.commit()

        paragraphs = extract_paragraphs(doc.stored_path)
        logger.info("Extracted %d paragraphs from %s", len(paragraphs), doc.original_filename)
        doc.total_paragraphs = len(paragraphs)
        doc.paragraphs_json = json.dumps([p.__dict__ if hasattr(p, '__dict__') else str(p) for p in paragraphs], ensure_ascii=False)
        db.commit()

        # 2. Analyze paragraphs
        doc.status = "analyzing"
        db.commit()

        analysis_result = await analyze_paragraphs(paragraphs, provider)
        analyzed: list[AnalyzedParagraph] = analysis_result.paragraphs
        total_steps = sum(len(ap.steps) for ap in analyzed)
        logger.info("Analyzed %d paragraphs, found %d steps", len(analyzed), total_steps)
        doc.total_steps = total_steps
        db.commit()

        # 3. Generate insights
        insights: DocumentInsights = await generate_insights(analyzed, provider)
        doc.insights_json = json.dumps(insights.__dict__, ensure_ascii=False, default=str)
        doc.analysis_stats = json.dumps({
            "total_paragraphs": len(paragraphs),
            "total_analyzed": len(analyzed),
            "total_steps": total_steps,
        }, ensure_ascii=False)

        # 4. Finalize
        doc.status = "ready"
        db.commit()
        db.refresh(doc)

        logger.info("Analysis complete for %s: %d steps, insights generated", document_id, total_steps)

        # Non-critical: store in MCP memory
        try:
            await store_pipeline_result(
                profile_id=document_id,
                stats={
                    "total_paragraphs": len(paragraphs),
                    "total_steps": total_steps,
                },
                profile_dict={
                    "version": insights.version,
                    "total_steps_analyzed": total_steps,
                    "source_document_count": 1,
                    "step_templates": insights.step_templates,
                    "vocabulary": insights.vocabulary,
                    "logic_rules": insights.logic_rules,
                },
                document_count=1,
            )
        except Exception as e:
            logger.warning("Failed to store pipeline result in MCP memory: %s", e)

        return doc

    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)[:1000]
        db.commit()
        logger.error("Analysis failed for %s: %s", document_id, e)
        raise
