"""
Stage 4: Аудит связности и полноты регламента.
Проверяет готовый документ на противоречия и пропуски.
Stage 6.5: поддержка profile_context для проверки по logic_rules профиля.
"""

import json
import logging
from typing import Optional
from app.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_AUDIT_CONTRADICTIONS = """Ты — аудитор корпоративной документации. Проверь регламент на следующие виды ошибок:

1. ТЕРМИНОЛОГИЧЕСКАЯ НЕСОГЛАСОВАННОСТЬ:
   - Одна и та же должность названа по-разному ("Главный инженер" → "Гл. инженер" → "Инженер")
   - Одна и та же ИТ-система названа по-разному ("1С:ERP" → "1С ERP" → "1С: ERP УХ")
   - Один и тот же документ назван по-разному

2. ЛОГИЧЕСКИЕ ПРОТИВОРЕЧИЯ:
   - Раздел A утверждает одно, раздел B — противоположное
   - Сроки в одном разделе противоречат срокам в другом
   - Ответственный в разделе A не совпадает с ответственным в разделе B

3. ПРОПУЩЕННЫЕ ЛОГИЧЕСКИЕ СВЯЗИ:
   - Раздел заканчивается, но не указано что происходит дальше
   - Результат этапа не передаётся следующему этапу

Для каждой найденной проблемы укажи:
- Раздел (номер): [номер]
- Тип: [терминология / логика / связь]
- Проблема: [описание]
- Исправление: [как исправить]

Если проблем нет: напиши "Проверка пройдена: противоречий не обнаружено."
"""

SYSTEM_PROMPT_AUDIT_COMPLETENESS = """Ты — аудитор корпоративной документации. Проверь, ПОЛНОСТЬЮ ли регламент описывает процесс от начала до конца.

Сравни ПЛАН документа с ФАКТИЧЕСКИМ содержанием и ответь на вопросы:
1. Все ли этапы из плана раскрыты в документе?
2. Нет ли «провалов» — этапов, где неясно что происходит дальше?
3. Каждый ли раздел содержит конкретные шаги (кто, что, как, когда)?
4. Нет ли этапов, которые описаны поверхностно (меньше 5 шагов)?

Для каждой найденной проблемы:
- Раздел: [номер]
- Проблема: [что пропущено или что неполно]
- Рекомендация: [что добавить]

Если всё в порядке: напиши "Проверка пройдена: все этапы раскрыты."
"""


async def audit_document(
    provider: BaseLLMProvider,
    topic: str,
    full_document_text: str,
    plan_text: str,
    profile_context: Optional[str] = None,
) -> dict:
    """
    Провести аудит готового документа.
    
    Args:
        provider: LLM-провайдер.
        topic: Тема регламента.
        full_document_text: Полный текст готового документа.
        plan_text: План документа.
        profile_context: Опциональный контекст профиля компании (logic_rules).
    
    Returns:
        {
            "contradictions": {...},
            "completeness": {...},
            "has_issues": bool,
            "summary": str
        }
    """
    logger.info("Stage 4a: Checking contradictions")

    contradictions_prompt = (
        f"Проверь этот корпоративный регламент на противоречия "
        f"и терминологическую несогласованность.\n\n"
        f"Тема: {topic}\n\n"
        f"ТЕКСТ РЕГЛАМЕНТА:\n{full_document_text}"
    )

    # Инъекция профиля компании для аудита по logic_rules
    if profile_context:
        contradictions_prompt += (
            f"\n\n{profile_context}\n\n"
            f"Проверь соответствие регламента правилам логики из профиля компании. "
            f"Убедись, что все обязательные элементы (role, action, deadline) присутствуют."
        )

    contradictions = await provider.generate(
        prompt=contradictions_prompt,
        system_prompt=SYSTEM_PROMPT_AUDIT_CONTRADICTIONS,
        temperature=0.3,
        max_tokens=2048,
    )
    
    logger.info("Stage 4b: Checking completeness")
    
    completeness_prompt = (
        f"Проверь полноту описания процесса в регламенте.\n\n"
        f"Тема: {topic}\n\n"
        f"ПЛАН ДОКУМЕНТА:\n{plan_text}\n\n"
        f"ТЕКСТ РЕГЛАМЕНТА:\n{full_document_text}"
    )

    if profile_context:
        completeness_prompt += (
            f"\n\n{profile_context}\n\n"
            f"Убедись, что все этапы раскрыты с использованием терминологии из профиля компании."
        )

    completeness = await provider.generate(
        prompt=completeness_prompt,
        system_prompt=SYSTEM_PROMPT_AUDIT_COMPLETENESS,
        temperature=0.3,
        max_tokens=2048,
    )
    
    has_issues = "Проверка пройдена" not in contradictions or "Проверка пройдена" not in completeness
    if "Проверка пройдена" in contradictions:
        contradictions_summary = "Противоречий не обнаружено"
    else:
        contradictions_summary = contradictions[:500] + "..." if len(contradictions) > 500 else contradictions
    if "Проверка пройдена" in completeness:
        completeness_summary = "Полнота в порядке"
    else:
        completeness_summary = completeness[:500] + "..." if len(completeness) > 500 else completeness
    
    return {
        "contradictions": {"raw": contradictions, "summary": contradictions_summary},
        "completeness": {"raw": completeness, "summary": completeness_summary},
        "has_issues": has_issues,
        "summary": f"Аудит завершён. Противоречия: {contradictions_summary[:100]}. Полнота: {completeness_summary[:100]}."
    }
