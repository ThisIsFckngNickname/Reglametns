"""
Stage 5: Сборка финального .docx из разделов регламента.
"""

import logging
import os
from typing import List
from app.services.docx_builder import build_docx, make_filename

logger = logging.getLogger(__name__)


def assemble_document(
    topic: str,
    sections: List[dict],
) -> str:
    """
    Склеить все разделы в единый .docx файл.
    
    Args:
        topic: Тема регламента (для имени файла)
        sections: Список секций [{title, content, section_number}, ...]
    
    Returns:
        Путь к созданному .docx файлу
    """
    # Сортируем по номеру раздела
    sorted_sections = sorted(sections, key=lambda s: s["section_number"])
    
    # Собираем полный текст
    full_text_parts = []
    
    for sec in sorted_sections:
        title = sec.get("title", "")
        content = sec.get("content", "")
        if title and content:
            full_text_parts.append(f"# {title}\n\n{content}")
        elif content:
            full_text_parts.append(content)
    
    full_text = "\n\n---\n\n".join(full_text_parts)
    
    if not full_text.strip():
        raise ValueError("No content to assemble - all sections are empty")
    
    # Добавляем финальную строку
    from datetime import datetime
    full_text += f"\n\n---\n\n*Документ сгенерирован автоматически, {datetime.now().strftime('%d.%m.%Y')}*"
    
    # Создаём .docx
    filename = make_filename(topic)
    docx_path = build_docx(full_text, filename)
    
    logger.info("Stage 5: Assembled document -> %s (%d sections)", docx_path, len(sorted_sections))
    return docx_path
