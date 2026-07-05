"""
Stage 2: Генерация аннотаций для каждого раздела плана.
Stage 6.5: поддержка profile_context для инъекции профиля компании.
"""

import logging
import re
from typing import Optional
from app.providers.base import BaseLLMProvider
from app.services.stage_1_planner import plan_to_text

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_ANNOTATOR = """Ты — методолог корпоративных регламентов. Для каждого раздела плана напиши КРАТКУЮ АННОТАЦИЮ (3-5 предложений).

Аннотация должна содержать:
1. Какие КОНКРЕТНЫЕ ДОЛЖНОСТИ участвуют в этом разделе
2. Какие ИТ-СИСТЕМЫ задействованы (1С: ERP, 1С: Документооборот, Excel и т.д.)
3. Какие ДОКУМЕНТЫ создаются в этом разделе (акты, отчёты, журналы)
4. Какие КЛЮЧЕВЫЕ ШАГИ выполняются
5. Какие СРОКИ/НОРМАТИВЫ применяются

Цель аннотаций:
- Другие разделы должны "знать", что происходит в этом разделе
- Аннотации предотвращают дублирование и противоречия
- Каждый раздел получает контекст всего документа ещё до начала генерации

ФОРМАТ ВЫВОДА:
Сохрани структуру плана и для каждого раздела добавь аннотацию на отдельной строке после названия:

## План документа: [Название]

1. [Название раздела 1]
   Аннотация: [текст аннотации]
   1.1 [Подраздел]
      Аннотация: [текст аннотации]
2. [Название раздела 2]
   Аннотация: [текст аннотации]
..."""


async def generate_annotations(
    provider: BaseLLMProvider,
    topic: str,
    plan_text: str,
    parsed_plan: list[dict],
    profile_context: Optional[str] = None,
) -> tuple[list[dict], str]:
    """
    Сгенерировать аннотации для всех разделов плана.
    
    Args:
        provider: LLM-провайдер.
        topic: Тема регламента.
        plan_text: Текстовое представление плана.
        parsed_plan: Структурированный план.
        profile_context: Опциональный контекст профиля компании (roles, systems, documents).
    
    Returns:
        (plan_with_annotations, raw_response)
        plan_with_annotations: тот же parsed_plan, но с полем "annotation" у каждого раздела
    """
    context_parts = [f'Вот план регламента на тему "{topic}":\n\n{plan_text}']
    context_parts.append(
        '\n\nДля каждого раздела и подраздела напиши аннотацию (3-5 предложений) по указанным правилам.'
    )

    # Инъекция профиля компании
    if profile_context:
        context_parts.append(f"\n\n{profile_context}")
        context_parts.append(
            "\n\nИспользуй указанные в профиле компании типовые должности, системы и документы "
            "при составлении аннотаций. Упомяни конкретные роли и системы из профиля."
        )

    user_prompt = "".join(context_parts)
    
    logger.info("Stage 2: Generating annotations for plan (%d sections)", len(parsed_plan))
    raw = await provider.generate(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT_ANNOTATOR,
        temperature=0.7,
        max_tokens=4096,
    )
    
    plan_with_annotations = _parse_annotations(raw, parsed_plan)
    return plan_with_annotations, raw


def _parse_annotations(raw: str, original_plan: list[dict]) -> list[dict]:
    """Распарсить аннотации из ответа LLM."""
    result = []
    sections_data = {}
    current_section_num = None
    current_annotation = []
    
    for line in raw.split("\n"):
        line = line.strip()
        
        main_match = re.match(r'^(\d+)\.\s+(.+)$', line)
        if main_match:
            if current_section_num is not None and current_annotation:
                sections_data[current_section_num] = " ".join(current_annotation)
            current_section_num = int(main_match.group(1))
            current_annotation = []
            continue
        
        annot_match = re.match(r'^Аннотация:\s*(.+)$', line, re.IGNORECASE)
        if annot_match:
            current_annotation.append(annot_match.group(1))
    
    if current_section_num is not None and current_annotation:
        sections_data[current_section_num] = " ".join(current_annotation)
    
    # Merge annotations into plan
    for section in original_plan:
        s = dict(section)
        s["annotation"] = sections_data.get(s["number"], "")
        if "children" in s:
            s["children"] = [dict(c) for c in s["children"]]
        result.append(s)
    
    return result



