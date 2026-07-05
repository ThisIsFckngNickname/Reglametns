"""
Stage 1: Генерация плана (оглавления) регламента.
Stage 6.5: поддержка profile_context для инъекции профиля компании.
"""

import logging
import re
from typing import Optional
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PLANNER = """Ты — методолог корпоративных регламентов. Твоя задача — составить ДЕТАЛЬНОЕ оглавление (план) документа регламента на указанную тему.

План должен охватывать ВЕСЬ процесс от начала до конца, включая:
- Подготовительные этапы (планирование, назначение ответственных)
- Основные этапы (в хронологическом порядке)
- Контрольные этапы (проверки, аудит)
- Заключительные этапы (отчётность, архивирование)
- Исключительные ситуации (действия при отклонениях)

ТРЕБОВАНИЯ К ПЛАНУ:
1. Минимум 6 (шесть) разделов, максимум 15 (пятнадцать) разделов.
2. Каждый раздел — логический этап процесса.
3. Используй иерархию:
   - 1. Первый раздел
   - 1.1 Подраздел первого (опционально)
   - 2. Второй раздел
4. Не используй подразделы глубже 2 уровня (только 1.1, 1.2 — не 1.1.1).
5. Названия разделов должны быть ИНФОРМАТИВНЫМИ (не "Раздел 1", а "Планирование и подготовка").
6. Не добавляй "Приложения" как раздел — это будет добавлено автоматически.

ФОРМАТ ВЫВОДА (строго):
## План документа: [Краткое название регламента]

1. [Название раздела 1]
   1.1 [Подраздел (опционально)]
   1.2 [Подраздел (опционально)]
2. [Название раздела 2]
3. [Название раздела 3]
   3.1 [Подраздел]
..."""


async def generate_plan(
    provider: BaseLLMProvider,
    topic: str,
    profile_context: Optional[str] = None,
) -> tuple[list[dict], str]:
    """
    Сгенерировать план (оглавление) регламента.
    
    Args:
        provider: LLM-провайдер.
        topic: Тема регламента.
        profile_context: Опциональный контекст профиля компании (vocabulary, section_patterns).
    
    Returns:
        (parsed_plan, raw_response)
        parsed_plan: [{"number": 1, "title": "...", "children": [
            {"number": 1.1, "title": "..."}
        ]}, ...]
    """
    context_parts = [f'Составь оглавление регламента на тему: "{topic}"']
    context_parts.append(
        "\n\nПлан должен полностью описывать процесс от начала до конца. "
        "Не выдумывай тем, которых нет в регламенте — только то, что действительно относится к процессу."
    )

    # Инъекция профиля компании
    if profile_context:
        context_parts.append(f"\n\n{profile_context}")
        context_parts.append(
            "\n\nИспользуй типовые должности и термины из профиля компании. "
            "Придерживайся паттернов разделов, указанных в профиле."
        )

    user_prompt = "".join(context_parts)
    
    logger.info("Stage 1: Generating plan for topic='%s'", topic)
    raw = await provider.generate(
        prompt=user_prompt,
        system_prompt=SYSTEM_PROMPT_PLANNER,
        temperature=0.7,
        max_tokens=4096,
    )
    
    plan = _parse_plan(raw)
    if len(plan) < 3:
        logger.warning("Plan too short (%d sections), retrying...", len(plan))
        raw = await provider.generate(
            prompt=user_prompt + "\n\nВАЖНО: В плане должно быть минимум 6 (шесть) разделов!",
            system_prompt=SYSTEM_PROMPT_PLANNER,
            temperature=0.7,
            max_tokens=4096,
        )
        plan = _parse_plan(raw)
    
    return plan, raw


def _parse_plan(raw: str) -> list[dict]:
    """Распарсить план из markdown-ответа LLM в структурированный список."""
    sections = []
    current_main = None
    
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        
        # Main section: "1. Название" or "1. Название раздела"
        main_match = re.match(r'^(\d+)\.\s+(.+)$', line)
        if main_match:
            num = int(main_match.group(1))
            title = main_match.group(2).strip()
            current_main = {
                "number": num,
                "title": title,
                "children": []
            }
            sections.append(current_main)
            continue
        
        # Subsection: "   1.1 Название" or "1.1 Название"
        sub_match = re.match(r'^\s*(\d+)\.(\d+)\s+(.+)$', line)
        if sub_match and current_main is not None:
            sub_num = int(sub_match.group(2))
            sub_title = sub_match.group(3).strip()
            current_main["children"].append({
                "number": float(f"{current_main['number']}.{sub_num}"),
                "title": sub_title,
            })
    
    return sections


def plan_to_text(plan: list[dict]) -> str:
    """Преобразовать план в текст."""
    lines = []
    for section in plan:
        num = section["number"]
        title = section["title"]
        ann = section.get("annotation", "")
        lines.append(f"{num}. {title}")
        if ann:
            lines.append(f"   Аннотация: {ann}")
        for child in section.get("children", []):
            cnum = child["number"]
            ctitle = child["title"]
            cann = child.get("annotation", "")
            lines.append(f"   {cnum}. {ctitle}")
            if cann:
                lines.append(f"      Аннотация: {cann}")
    return "\n".join(lines)
