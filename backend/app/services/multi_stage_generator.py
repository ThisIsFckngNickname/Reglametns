"""
MultiStageGenerator — главный оркестратор многоэтапной генерации.
Stage 4.4: полный цикл: план → аннотации → разделы → аудит → сборка .docx
"""

import json
import logging
import os
from typing import Optional
from app.database import SessionLocal
from app.models.session import GenerationSession
from app.models.plan import GenerationPlan
from app.models.section import DocumentSection
from app.providers.base import BaseLLMProvider
from app.services.stage_1_planner import generate_plan, plan_to_text
from app.services.stage_2_annotator import generate_annotations
from app.services.stage_3_writer import generate_section
from app.services.stage_4_auditor import audit_document
from app.services.stage_5_assembler import assemble_document

logger = logging.getLogger(__name__)

GENERATED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generated")


async def run_multi_stage_generation(
    generation_session_id: str,
    provider: BaseLLMProvider,
    profile_context: Optional[str] = None,
):
    """Запустить полный цикл multi-stage генерации."""
    db = SessionLocal()
    try:
        generation_session = db.query(GenerationSession).filter(
            GenerationSession.id == generation_session_id
        ).first()
        if not generation_session:
            logger.error("Session %s not found", generation_session_id)
            return

        # === Этап 1: План ===
        generation_session.status = "planning"
        generation_session.current_stage = "planning"
        generation_session.stage_progress = 0
        db.commit()

        parsed_plan, raw_plan = await generate_plan(
            provider,
            generation_session.topic,
            profile_context=profile_context,
        )
        plan_text = plan_to_text(parsed_plan)

        generation_plan = GenerationPlan(
            session_id=generation_session.id,
            plan_json=json.dumps(parsed_plan, ensure_ascii=False),
            raw_response=raw_plan,
        )
        db.add(generation_plan)
        generation_session.total_sections = len(parsed_plan)
        generation_session.stage_progress = 15
        db.commit()
        logger.info("Stage 1 complete: %d sections", len(parsed_plan))

        # === Этап 2: Аннотации ===
        generation_session.status = "annotating"
        generation_session.current_stage = "annotating"
        generation_session.stage_progress = 25
        db.commit()

        plan_with_annotations, raw_annotations = await generate_annotations(
            provider,
            generation_session.topic,
            raw_plan,
            parsed_plan,
            profile_context=profile_context,
        )
        plan_text_with_ann = plan_to_text(plan_with_annotations)
        generation_plan.plan_json = json.dumps(plan_with_annotations, ensure_ascii=False)
        generation_session.stage_progress = 40
        db.commit()
        logger.info("Stage 2 complete")

        # === Этап 3: Поразделная генерация ===
        generation_session.status = "generating"
        generation_session.current_stage = "generating"
        generation_session.total_sections = len(plan_with_annotations)
        generation_session.completed_sections = 0
        db.commit()

        previous_section_tail = ""
        all_sections_data = []

        for i, section in enumerate(plan_with_annotations):
            section_number = i + 1
            section_title = section.get("title", f"Раздел {section_number}")
            section_annotation = section.get("annotation", "")

            doc_section = DocumentSection(
                session_id=generation_session.id,
                section_number=section_number,
                title=section_title,
                annotation=section_annotation,
                status="generating",
            )
            db.add(doc_section)
            db.commit()

            try:
                content = await generate_section(
                    provider=provider,
                    topic=generation_session.topic,
                    section_number=section_number,
                    section_title=section_title,
                    section_annotation=section_annotation,
                    plan_with_annotations=plan_text_with_ann,
                    previous_section_tail=previous_section_tail,
                    profile_context=profile_context,
                )
                doc_section.content = content
                doc_section.status = "completed"
                previous_section_tail = _get_tail(content)
                all_sections_data.append({
                    "section_number": section_number,
                    "title": section_title,
                    "content": content,
                })
            except Exception as e:
                logger.error("Section %d failed: %s", section_number, e)
                doc_section.status = "failed"
                doc_section.content = f"[Ошибка генерации: {e}]"

            generation_session.completed_sections = i + 1
            progress = 40 + int(((i + 1) / len(plan_with_annotations)) * 35)
            generation_session.stage_progress = min(progress, 75)
            db.commit()

        # Сохраняем полный текст
        full_text_parts = [f"# {s['title']}\n\n{s['content']}" for s in all_sections_data if s.get("content")]
        full_text = "\n\n---\n\n".join(full_text_parts)
        generation_plan.raw_response = full_text
        db.commit()

        if not all_sections_data:
            raise ValueError("No sections were generated successfully")

        logger.info("Stage 3 complete: %d sections", len(all_sections_data))

        # === Этап 4: Аудит ===
        generation_session.status = "auditing"
        generation_session.current_stage = "auditing"
        generation_session.stage_progress = 80
        db.commit()

        audit_result = await audit_document(
            provider=provider,
            topic=generation_session.topic,
            full_document_text=full_text,
            plan_text=plan_text_with_ann,
            profile_context=profile_context,
        )
        logger.info("Stage 4 complete: has_issues=%s", audit_result.get("has_issues"))

        # === Этап 5: Сборка .docx ===
        generation_session.status = "assembling"
        generation_session.current_stage = "assembling"
        generation_session.stage_progress = 90
        db.commit()

        os.makedirs(GENERATED_DIR, exist_ok=True)
        docx_path = assemble_document(
            topic=generation_session.topic,
            sections=all_sections_data,
        )

        # Обновляем статус сессии
        generation_session.status = "completed"
        generation_session.current_stage = "completed"
        generation_session.stage_progress = 100
        from datetime import datetime
        generation_session.completed_at = datetime.utcnow()
        generation_session.document_id = all_sections_data[0].get("document_id", "")
        
        # Создаём запись в documents
        from app.models.document import Document
        existing_doc = Document(
            topic=generation_session.topic,
            provider_used=generation_session.provider_used,
            prompt=full_text[:500],
            raw_response=full_text,
            docx_path=docx_path,
            status="completed",
        )
        db.add(existing_doc)
        db.flush()
        generation_session.document_id = existing_doc.id
        db.commit()

        logger.info("Multi-stage generation complete: %s", docx_path)

    except Exception as e:
        logger.error("Multi-stage generation failed: %s", e)
        try:
            generation_session = db.query(GenerationSession).filter(
                GenerationSession.id == generation_session_id
            ).first()
            if generation_session:
                generation_session.status = "failed"
                generation_session.error_message = str(e)
                generation_session.stage_progress = 0
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()


def _get_tail(text: str, max_chars: int = 800) -> str:
    """Вернуть хвост текста (последние ~800 символов) для контекста связки."""
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    first_newline = tail.find("\n")
    if first_newline > 0:
        tail = tail[first_newline + 1:]
    return tail.strip()
