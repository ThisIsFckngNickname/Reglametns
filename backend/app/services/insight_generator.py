"""
insight_generator — синтез инсайтов для качества генерации из проанализированных параграфов.

Основная функция:
    generate_insights(all_steps, provider) -> DocumentInsights

Логика:
    1. Сбор всех Step[] из AnalyzedParagraph
    2. LLM-синтез: формирование промпта, вызов LLM, парсинг JSON
    3. Fallback: статистический анализ при недоступности LLM
    4. Валидация результатов
"""

from __future__ import annotations

import json
import logging
import random
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any

from app.providers.base import BaseLLMProvider
from app.services.paragraph_analyzer import Step, AnalyzedParagraph
from app.utils.json_utils import try_extract_json_object

logger = logging.getLogger(__name__)


# ── Data structures ───────────────────────────────────────


@dataclass
class DocumentInsights:
    """
    Инсайты по документу для улучшения качества генерации регламентов.

    Содержит шаблоны предложений, словарь терминов,
    правила логики и статистику, извлечённые из документа.
    """
    version: int = 2
    total_paragraphs: int = 0
    total_steps: int = 0
    step_templates: list[str] = field(default_factory=list)
    """Типовые шаблоны предложений с плейсхолдерами (для генератора)."""
    vocabulary: dict = field(default_factory=dict)
    """Словарь терминов: roles, actions, deadlines, methods, conditions, documents, consequences."""
    logic_rules: dict = field(default_factory=dict)
    """Правила типичной структуры шага."""
    stats: dict = field(default_factory=dict)
    """Статистика заполненности полей."""


# ── Prompt ────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "Ты — методолог корпоративных документов. "
    "Твоя задача — анализировать массив логических шагов из регламентов "
    "и выделять шаблоны, терминологию и правила для генерации новых документов."
)

_USER_PROMPT_TEMPLATE = """
Проанализируй логические шаги из регламента и выдели:
1. step_templates — 2-5 наиболее частотных шаблонов предложений с плейсхолдерами.
   Пример: "[Должность] [действие] в срок [срок] посредством [способ]"

2. vocabulary — словарь терминов по категориям:
   - roles: должности с частотностью
   - actions: действия с частотностью
   - deadlines: типичные сроки (массив)
   - methods: системы/способы (массив)
   - conditions: условия (массив)
   - documents: документы (массив)
   - consequences: последствия (массив)

3. logic_rules — правила структуры шага:
   - role_required: true/false
   - deadline_required: true/false
   - typical_order: ["role", "action", "deadline", "method"]
   - conditional_logic: true/false
   - has_consequences: true/false

Всего шагов: {total_steps}

Данные шагов:
{steps_json}

Ответ строго в JSON:
{{
  "step_templates": ["..."],
  "vocabulary": {{
    "roles": {{"Должность": 5}},
    "actions": {{"действие": 3}},
    "deadlines": ["..."],
    "methods": ["..."],
    "conditions": ["..."],
    "documents": ["..."],
    "consequences": ["..."]
  }},
  "logic_rules": {{
    "role_required": true,
    "deadline_required": false,
    "typical_order": ["role", "action", "deadline", "method"],
    "conditional_logic": false,
    "has_consequences": false
  }}
}}
"""


# ── Helpers ───────────────────────────────────────────────


def _collect_steps(paragraphs: list[AnalyzedParagraph]) -> list[Step]:
    """Собирает все Step из списка проанализированных параграфов."""
    all_steps: list[Step] = []
    for ap in paragraphs:
        all_steps.extend(ap.steps)
    return all_steps


def _steps_to_json(steps: list[Step]) -> str:
    """Сериализует список Step в JSON (только заполненные поля)."""
    items = []
    for s in steps:
        d = {}
        for field in ("role", "action", "deadline", "method", "condition", "document", "consequence"):
            val = getattr(s, field, None)
            if val:
                d[field] = val
        items.append(d)
    return json.dumps(items, ensure_ascii=False, indent=2)


def _sample_steps(steps: list[Step], max_steps: int = 500) -> list[Step]:
    """Семплинг при большом количестве шагов: первые 250 + случайные 250."""
    if len(steps) <= max_steps:
        return steps
    first_250 = steps[:250]
    remaining = steps[250:]
    sample_size = min(250, max_steps - 250)
    if len(remaining) <= sample_size:
        return first_250 + remaining
    sampled = random.sample(remaining, sample_size)
    return first_250 + sampled


def _statistical_analysis(steps: list[Step]) -> dict:
    """Чисто статистический анализ шагов (без LLM)."""
    roles = Counter(s.role for s in steps if s.role)
    actions = Counter(s.action for s in steps if s.action)
    deadlines = list({s.deadline for s in steps if s.deadline})
    methods = list({s.method for s in steps if s.method})
    conditions = list({s.condition for s in steps if s.condition})
    documents = list({s.document for s in steps if s.document})
    consequences = list({s.consequence for s in steps if s.consequence})

    templates = ["[Должность] [действие]"]
    if deadlines:
        templates.append("[Должность] [действие] в срок [срок]")
    if methods:
        templates.append("[Должность] [действие] посредством [способ]")
    if conditions:
        templates.append("При [условие] [должность] обязан [действие]")
    if consequences:
        templates.append("[Должность] [действие] — в противном случае [последствие]")

    return {
        "step_templates": templates[:5],
        "vocabulary": {
            "roles": dict(roles.most_common(50)),
            "actions": dict(actions.most_common(50)),
            "deadlines": deadlines[:20],
            "methods": methods[:20],
            "conditions": conditions[:20],
            "documents": documents[:20],
            "consequences": consequences[:20],
        },
        "logic_rules": {
            "role_required": bool(roles),
            "deadline_required": bool(deadlines),
            "typical_order": ["role", "action", "deadline", "method"],
            "conditional_logic": bool(conditions),
            "has_consequences": bool(consequences),
        },
    }


# ── Main function ─────────────────────────────────────────


async def generate_insights(
    paragraphs: list[AnalyzedParagraph],
    provider: BaseLLMProvider,
) -> DocumentInsights:
    """
    Генерирует инсайты для качества генерации на основе проанализированных параграфов.

    Args:
        paragraphs: Результат analyze_paragraphs()
        provider: LLM-провайдер

    Returns:
        DocumentInsights с шаблонами, словарём и правилами
    """
    all_steps = _collect_steps(paragraphs)
    total_steps = len(all_steps)
    total_paragraphs = len(paragraphs)

    logger.info("Generating insights from %d paragraphs, %d steps", total_paragraphs, total_steps)

    if not all_steps:
        logger.warning("No steps found, returning empty insights")
        return DocumentInsights(
            version=2,
            total_paragraphs=total_paragraphs,
            total_steps=0,
        )

    # Пробуем LLM-синтез
    insight_data = await _llm_synthesis(all_steps, provider)

    # Fallback при ошибке LLM
    if insight_data is None:
        logger.info("LLM synthesis unavailable, using statistical fallback")
        insight_data = _statistical_analysis(all_steps)

    return DocumentInsights(
        version=2,
        total_paragraphs=total_paragraphs,
        total_steps=total_steps,
        step_templates=insight_data.get("step_templates", []),
        vocabulary=insight_data.get("vocabulary", {}),
        logic_rules=insight_data.get("logic_rules", {}),
    )


async def _llm_synthesis(
    steps: list[Step],
    provider: BaseLLMProvider,
) -> dict | None:
    """Пытается синтезировать инсайты через LLM."""
    sampled = _sample_steps(steps)
    steps_json = _steps_to_json(sampled)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        total_steps=len(steps),
        steps_json=steps_json,
    )

    logger.info("Synthesizing insights via %s (%d steps, sampled %d)", provider.name, len(steps), len(sampled))

    try:
        response = await provider.generate(
            prompt=user_prompt,
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )
    except Exception as e:
        logger.warning("LLM synthesis failed: %s", e)
        return None

    if not response or not response.strip():
        logger.warning("LLM returned empty response")
        return None

    parsed = try_extract_json_object(response)
    if parsed is None:
        logger.warning("Failed to parse LLM response as JSON")
        return None

    required_keys = ["step_templates", "vocabulary", "logic_rules"]
    missing = [k for k in required_keys if k not in parsed]
    if missing:
        logger.warning("LLM response missing keys: %s", missing)
        return None

    return parsed
