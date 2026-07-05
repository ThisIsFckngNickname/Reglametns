"""
profile_synthesizer — синтез Paragraph Logic Profile из массива проанализированных параграфов.

Основная функция:
    synthesize_profile(all_steps, provider, document_count) -> ParagraphLogicProfile

Логика:
    1. Сбор всех Step[] из всех AnalyzedParagraph
    2. LLM-синтез: формирование промпта, вызов LLM, парсинг JSON
    3. Семплинг при >500 шагов (первые 250 + случайные 250)
    4. Fallback: статистический анализ при недоступности LLM
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


# ──────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────


@dataclass
class ParagraphLogicProfile:
    """Профиль логики параграфов — шаблоны, словарь, правила."""

    version: int = 2
    """Версия профиля."""

    source_document_count: int = 0
    """Количество проанализированных документов."""

    total_steps_analyzed: int = 0
    """Общее количество проанализированных шагов."""

    step_templates: list[str] = field(default_factory=list)
    """Типовые шаблоны предложений с плейсхолдерами."""

    vocabulary: dict = field(default_factory=dict)
    """Словарь терминов, сгруппированный по категориям (roles, actions, deadlines, ...)."""

    logic_rules: dict = field(default_factory=dict)
    """Правила, описывающие типичную структуру шага."""

    section_patterns: dict = field(default_factory=dict)
    """Паттерны для разных типов разделов."""

    transition_patterns: list[str] = field(default_factory=list)
    """Типичные фразы-связки между параграфами."""


# ──────────────────────────────────────────────
# Prompt
# ──────────────────────────────────────────────

_SYNTHESIS_SYSTEM_PROMPT = (
    "Ты — методолог корпоративных документов. "
    "Твоя задача — анализировать массив распознанных логических шагов "
    "из регламентов компании и синтезировать ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ."
)

_SYNTHESIS_USER_PROMPT_TEMPLATE = """
Проанализируй массив распознанных логических шагов из регламентов компании
и синтезируй ПРОФИЛЬ ЛОГИКИ ПАРАГРАФОВ.

Вот данные анализа {document_count} документов: всего {total_steps} шагов.

Проанализированные шаги (в формате JSON):
{steps_json}

Извлеки в строгом JSON (без пояснений):

1. step_templates — 2-5 наиболее частотных шаблонов предложений с плейсхолдерами.
   Определи ОБЩУЮ ФОРМУЛУ, по которой строятся шаги.
   Пример: "[Должность] [действие] в срок [срок] посредством [способ]"
   Или: "При [условие] [должность] обязан [действие] в течение [срок]"

2. vocabulary — словарь терминов, сгруппированный по категориям:
   - roles: все уникальные должности/роли (с частотностью как числом)
   - actions: все уникальные действия (с частотностью)
   - deadlines: типичные сроки (массив строк)
   - methods: все упомянутые системы/способы (массив строк)
   - conditions: типичные условия-триггеры (массив строк)
   - documents: типы документов (массив строк)
   - consequences: типичные последствия (массив строк)

3. logic_rules — правила, описывающие типичную структуру шага:
   - "role_required": true/false
   - "deadline_required": true/false
   - "typical_order": ["role", "action", "deadline", "method"]
   - "conditional_logic": true/false
   - "has_consequences": true/false

4. section_patterns — паттерны для разных типов разделов (объект, ключи — названия разделов)

5. transition_patterns — типичные фразы-связки между параграфами (массив строк)

Ответ строго в JSON:
{{
  "version": 2,
  "source_document_count": 3,
  "total_steps_analyzed": 245,
  "step_templates": ["[Должность] [действие] в срок [срок] посредством [способ]"],
  "vocabulary": {{
    "roles": {{"Начальник АЗС": 12, "Бухгалтер": 8}},
    "actions": {{"осуществляет приём": 10, "составляет отчёт": 7}},
    "deadlines": ["ежедневно до 10:00", "ежемесячно до 5 числа"],
    "methods": ["1С:Предприятие", "бумажный носитель"],
    "conditions": ["при отклонении более 5%", "в случае несоответствия"],
    "documents": ["акт приёма-передачи", "журнал учёта"],
    "consequences": ["дисциплинарная ответственность"]
  }},
  "logic_rules": {{
    "role_required": true,
    "deadline_required": false,
    "typical_order": ["role", "action", "deadline", "method"],
    "conditional_logic": true,
    "has_consequences": false
  }},
  "section_patterns": {{}},
  "transition_patterns": ["Во исполнение п. X...", "На основании..."]
}}
"""


# ──────────────────────────────────────────────
# Step collection
# ──────────────────────────────────────────────


def _collect_all_steps(
    analyzed_paragraphs: list[tuple[int, AnalyzedParagraph]],
) -> list[Step]:
    """Собирает все Step из списка (sequence, AnalyzedParagraph)."""
    all_steps: list[Step] = []
    for _seq, ap in analyzed_paragraphs:
        all_steps.extend(ap.steps)
    return all_steps


def _steps_to_json(steps: list[Step]) -> str:
    """Сериализует список Step в JSON."""
    steps_dicts = []
    for s in steps:
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
    return json.dumps(steps_dicts, ensure_ascii=False, indent=2)


def _sample_steps(steps: list[Step], max_steps: int = 500) -> list[Step]:
    """Семплинг: первые 250 + случайные 250 (если шагов > max_steps)."""
    if len(steps) <= max_steps:
        return steps

    first_250 = steps[:250]
    remaining = steps[250:]

    # Если осталось меньше 250, берём все
    sample_size = min(250, max_steps - 250)
    if len(remaining) <= sample_size:
        return first_250 + remaining

    sampled = random.sample(remaining, sample_size)
    return first_250 + sampled


# ──────────────────────────────────────────────
# JSON parsing helpers
# ──────────────────────────────────────────────


def _merge_profile_data(
    base: ParagraphLogicProfile,
    data: dict,
    document_count: int,
    total_steps: int,
) -> ParagraphLogicProfile:
    """Заполняет профиль из словаря, возвращая новый объект."""
    profile = ParagraphLogicProfile(
        version=data.get("version", 2),
        source_document_count=data.get("source_document_count", document_count),
        total_steps_analyzed=data.get("total_steps_analyzed", total_steps),
        step_templates=data.get("step_templates", base.step_templates),
        vocabulary=data.get("vocabulary", base.vocabulary),
        logic_rules=data.get("logic_rules", base.logic_rules),
        section_patterns=data.get("section_patterns", base.section_patterns),
        transition_patterns=data.get("transition_patterns", base.transition_patterns),
    )
    return profile


# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────


def validate_profile(profile: ParagraphLogicProfile) -> list[str]:
    """
    Валидирует структуру профиля.

    Returns
    -------
    list[str]
        Список предупреждений (пустой, если профиль валиден).
    """
    warnings: list[str] = []

    if not profile.step_templates:
        warnings.append("No step templates found")

    vocab = profile.vocabulary or {}
    if not vocab.get("roles"):
        warnings.append("No roles in vocabulary")
    if not vocab.get("actions"):
        warnings.append("No actions in vocabulary")

    if not profile.logic_rules:
        warnings.append("No logic rules found")

    if profile.total_steps_analyzed <= 0:
        warnings.append("total_steps_analyzed is 0 or negative")

    return warnings


# ──────────────────────────────────────────────
# LLM Synthesis
# ──────────────────────────────────────────────


async def _llm_synthesis(
    steps_data: list[Step],
    provider: BaseLLMProvider,
    document_count: int,
) -> ParagraphLogicProfile | None:
    """
    Пытается синтезировать профиль через LLM.

    Returns
    -------
    ParagraphLogicProfile | None
        Профиль, или None при ошибке.
    """
    total_steps = len(steps_data)

    # Семплинг
    sampled = _sample_steps(steps_data)
    steps_json = _steps_to_json(sampled)

    # Формируем промпт
    user_prompt = _SYNTHESIS_USER_PROMPT_TEMPLATE.format(
        document_count=document_count,
        total_steps=total_steps,
        steps_json=steps_json,
    )

    logger.info(
        "Synthesizing profile via %s (%d steps, sampled %d)",
        provider.name,
        total_steps,
        len(sampled),
    )

    try:
        response = await provider.generate(
            prompt=user_prompt,
            system_prompt=_SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2048,
        )
    except Exception as e:
        logger.warning("LLM synthesis failed: %s", e)
        return None

    if not response or not response.strip():
        logger.warning("LLM returned empty response")
        return None

    # Парсим JSON
    parsed = try_extract_json_object(response)
    if parsed is None:
        logger.warning("Failed to parse LLM response as JSON")
        return None

    # Проверяем обязательные ключи
    required_keys = [
        "step_templates",
        "vocabulary",
        "logic_rules",
    ]
    missing = [k for k in required_keys if k not in parsed]
    if missing:
        logger.warning("LLM response missing keys: %s", missing)
        return None

    # Собираем профиль
    base = ParagraphLogicProfile(
        version=2,
        source_document_count=document_count,
        total_steps_analyzed=total_steps,
    )
    profile = _merge_profile_data(base, parsed, document_count, total_steps)
    return profile


# ──────────────────────────────────────────────
# Statistical Fallback
# ──────────────────────────────────────────────


def statistical_fallback(all_steps: list[Step]) -> ParagraphLogicProfile:
    """
    Строит базовый профиль с помощью статистического анализа (без LLM).

    Parameters
    ----------
    all_steps : list[Step]
        Все извлечённые шаги.

    Returns
    -------
    ParagraphLogicProfile
        Профиль на основе частотного анализа.
    """
    roles = Counter(s.role for s in all_steps if s.role)
    actions = Counter(s.action for s in all_steps if s.action)
    deadlines = list({s.deadline for s in all_steps if s.deadline})
    methods = list({s.method for s in all_steps if s.method})
    conditions = list({s.condition for s in all_steps if s.condition})
    documents = list({s.document for s in all_steps if s.document})
    consequences = list({s.consequence for s in all_steps if s.consequence})

    # Типовые шаблоны на основе заполненности полей
    templates: list[str] = ["[Должность] [действие]"]
    if deadlines:
        templates.append("[Должность] [действие] в срок [срок]")
    if methods:
        templates.append("[Должность] [действие] посредством [способ]")
    if conditions:
        templates.append("При [условие] [должность] обязан [действие]")
    if consequences:
        templates.append("[Должность] [действие] — в противном случае [последствие]")

    return ParagraphLogicProfile(
        version=2,
        total_steps_analyzed=len(all_steps),
        step_templates=templates[:5],
        vocabulary={
            "roles": dict(roles.most_common(50)),
            "actions": dict(actions.most_common(50)),
            "deadlines": deadlines[:20],
            "methods": methods[:20],
            "conditions": conditions[:20],
            "documents": documents[:20],
            "consequences": consequences[:20],
        },
        logic_rules={
            "role_required": bool(roles),
            "deadline_required": bool(deadlines),
            "typical_order": ["role", "action", "deadline", "method"],
            "conditional_logic": bool(conditions),
            "has_consequences": bool(consequences),
        },
    )


# ──────────────────────────────────────────────
# Main function
# ──────────────────────────────────────────────


async def synthesize_profile(
    all_steps: list[tuple[int, AnalyzedParagraph]],
    provider: BaseLLMProvider,
    document_count: int = 1,
) -> ParagraphLogicProfile:
    """
    Синтезирует Paragraph Logic Profile из массива проанализированных параграфов.

    Parameters
    ----------
    all_steps : list[tuple[int, AnalyzedParagraph]]
        Все проанализированные параграфы с их последовательностью (sequence, paragraph).
    provider : BaseLLMProvider
        LLM-провайдер для синтеза.
    document_count : int
        Количество исходных документов.

    Returns
    -------
    ParagraphLogicProfile
        Синтезированный профиль логики параграфов.
    """
    # Собираем все Step
    steps_data = _collect_all_steps(all_steps)
    total_steps = len(steps_data)

    logger.info(
        "Synthesizing profile from %d paragraphs, %d steps across %d document(s)",
        len(all_steps),
        total_steps,
        document_count,
    )

    if not steps_data:
        logger.warning("No steps found, returning empty profile")
        return ParagraphLogicProfile(
            version=2,
            source_document_count=document_count,
            total_steps_analyzed=0,
        )

    # Пробуем LLM-синтез
    profile = await _llm_synthesis(steps_data, provider, document_count)

    # Fallback при ошибке LLM
    if profile is None:
        logger.info("LLM synthesis unavailable, using statistical fallback")
        profile = statistical_fallback(steps_data)
        # Добавляем метаданные документа
        profile.source_document_count = document_count

    # Валидируем
    warnings = validate_profile(profile)
    if warnings:
        logger.warning("Profile validation warnings: %s", warnings)

    logger.info(
        "Profile synthesized: v%d, %d templates, %d roles, %d actions",
        profile.version,
        len(profile.step_templates),
        len(profile.vocabulary.get("roles", {})),
        len(profile.vocabulary.get("actions", {})),
    )

    return profile


# ──────────────────────────────────────────────
# Verification (self-test)
# ──────────────────────────────────────────────


if __name__ == "__main__":
    import asyncio
    import sys

    async def test():
        from app.services.paragraph_extractor import extract_paragraphs
        from app.providers.ollama import OllamaProvider

        docx_path = r"E:\OCProj\Reglametns\Reglament GSM.docx"
        if len(sys.argv) > 1:
            docx_path = sys.argv[1]

        print(f"Extracting paragraphs from: {docx_path}")
        pars = extract_paragraphs(docx_path)
        body = [p for p in pars if not p.is_heading][:24]
        print(f"Extracted {len(pars)} paragraphs total, using first {len(body)} body paragraphs")

        print("Creating Ollama provider...")
        provider = OllamaProvider()

        # Сначала анализируем параграфы
        from app.services.paragraph_analyzer import analyze_paragraphs
        print("Starting paragraph analysis...")
        result = await analyze_paragraphs(body, provider)

        all_steps_data = []
        for ap in result.paragraphs:
            all_steps_data.append((ap.paragraph_index, ap))

        step_count = sum(len(ap.steps) for ap in result.paragraphs)
        print(f"Analyzed {len(result.paragraphs)} paragraphs, got {step_count} steps")

        if step_count == 0:
            print("\n[!] No steps found, trying statistical fallback directly")
            from app.services.paragraph_analyzer import Step
            dummy_steps = [
                Step(role="Начальник АЗС", action="осуществляет приём ГСМ"),
                Step(role="Бухгалтер", action="составляет отчёт", deadline="ежемесячно до 5 числа"),
            ]
            profile = statistical_fallback(dummy_steps)
            print(f"\n=== Fallback Profile ===")
            print(f"Version: {profile.version}")
            print(f"Templates: {profile.step_templates}")
            print(f"Roles: {profile.vocabulary.get('roles', {})}")
            print(f"Actions: {profile.vocabulary.get('actions', {})}")
            print(f"Logic rules: {profile.logic_rules}")
            print(f"Warnings: {validate_profile(profile)}")
            return

        # Синтезируем профиль
        print("\nSynthesizing profile...")
        profile = await synthesize_profile(
            all_steps_data,
            provider,
            document_count=1,
        )

        print(f"\n=== Synthesized Profile ===")
        print(f"Version: {profile.version}")
        print(f"Source documents: {profile.source_document_count}")
        print(f"Total steps analyzed: {profile.total_steps_analyzed}")
        print(f"\nStep templates ({len(profile.step_templates)}):")
        for i, tmpl in enumerate(profile.step_templates, 1):
            print(f"  {i}. {tmpl}")

        vocab = profile.vocabulary or {}
        print(f"\nRoles ({len(vocab.get('roles', {}))}):")
        for role, count in list(vocab.get("roles", {}).items())[:10]:
            print(f"  {role}: {count}")

        print(f"\nActions ({len(vocab.get('actions', {}))}):")
        for action, count in list(vocab.get("actions", {}).items())[:10]:
            print(f"  {action}: {count}")

        print(f"\nDeadlines: {vocab.get('deadlines', [])}")
        print(f"Methods: {vocab.get('methods', [])}")
        print(f"Conditions: {vocab.get('conditions', [])}")
        print(f"Documents: {vocab.get('documents', [])}")
        print(f"Consequences: {vocab.get('consequences', [])}")

        print(f"\nLogic rules:")
        for k, v in (profile.logic_rules or {}).items():
            print(f"  {k}: {v}")

        print(f"\nSection patterns: {profile.section_patterns}")
        print(f"Transition patterns ({len(profile.transition_patterns)}):")
        for tp in profile.transition_patterns:
            print(f"  - {tp}")

        # Валидация
        warnings = validate_profile(profile)
        if warnings:
            print(f"\n[!] Warnings: {warnings}")
        else:
            print("\n[OK] Profile validation passed")

        print("\n--- Done ---")

    asyncio.run(test())
