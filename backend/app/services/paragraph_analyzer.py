"""
paragraph_analyzer — LLM-анализ параграфов регламента с извлечением Step[].

Основная функция:
    analyze_paragraphs(paragraphs, provider) -> AnalysisResult

Логика:
    1. Фильтрация: только body-параграфы (не заголовки, не пустые)
    2. Батчинг: группы по 3 параграфа (batch_size=3)
    3. Для каждого батча: вызов LLM со структурированным промптом
    4. Парсинг ответа: JSON → list[dict] → list[Step]
    5. Fallback: если JSON невалидный — попытка regex
    6. Агрегация: сбор всех шагов, вычисление статистики
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Callable, Awaitable

from app.providers.base import BaseLLMProvider
from app.services.paragraph_extractor import ExtractedParagraph
from app.utils.json_utils import try_extract_json, safe_str

# Backward compatibility alias
_safe_str = safe_str

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────


@dataclass
class Step:
    """Один логический шаг инструкции из регламента."""

    role: str | None = None
    """Кто делает (должность / подразделение)."""

    action: str | None = None
    """Что делает (конкретное действие)."""

    deadline: str | None = None
    """Когда / в какой срок (периодичность или дедлайн)."""

    method: str | None = None
    """Как / в какой системе (способ выполнения, ИТ-система)."""

    condition: str | None = None
    """При каком условии выполняется действие."""

    document: str | None = None
    """Какой документ создаётся."""

    consequence: str | None = None
    """Что будет, если не выполнить действие."""


@dataclass
class AnalyzedParagraph:
    """Результат анализа одного параграфа."""

    paragraph_index: int
    """Индекс исходного параграфа (сквозной)."""

    original_text: str
    """Текст параграфа."""

    section_title: str | None
    """Название раздела, к которому относится параграф."""

    is_table_row: bool
    """True, если параграф извлечён из таблицы."""

    is_list_item: bool
    """True, если параграф — элемент списка."""

    steps: list[Step] = field(default_factory=list)
    """Извлечённые шаги (0, 1 или несколько)."""

    parse_error: bool = False
    """True, если при парсинге ответа LLM произошла ошибка."""


@dataclass
class AnalysisResult:
    """Результат анализа набора параграфов."""

    paragraphs: list[AnalyzedParagraph]
    """Проанализированные параграфы (каждый со своими шагами)."""

    stats: dict[str, Any] = field(default_factory=dict)
    """Статистика по заполненности полей."""


# ──────────────────────────────────────────────
# Prompt building
# ──────────────────────────────────────────────

_ANALYSIS_SYSTEM_PROMPT = """Ты — анализатор корпоративных регламентов. Твоя задача — извлекать из текста структурированные инструкции (шаги)."""

_ANALYSIS_USER_PROMPT_TEMPLATE = """
Проанализируй следующие параграфы из регламента.
Для каждого параграфа извлеки логические шаги (Step) — инструкции вида:
- КТО делает (role): должность или подразделение
- ЧТО делает (action): конкретное действие
- КОГДА/В КАКОЙ СРОК (deadline): периодичность или дедлайн
- КАК/В КАКОЙ СИСТЕМЕ (method): способ выполнения, ИТ-система
- ПРИ КАКОМ УСЛОВИИ (condition): условие для выполнения
- КАКОЙ ДОКУМЕНТ (document): что создаётся
- ЧТО БУДЕТ (consequence): последствия невыполнения

Один параграф может содержать 0, 1 или несколько шагов.
Если поле не указано в тексте — ставь null.

Ответь строго в формате JSON (массив объектов):
[
  {{
    "paragraph_index": 0,
    "steps": [
      {{
        "role": "Начальник АЗС" или null,
        "action": "осуществляет приём ГСМ",
        "deadline": "ежедневно до 10:00" или null,
        "method": "в системе 1С:Предприятие" или null,
        "condition": null,
        "document": null,
        "consequence": null
      }}
    ]
  }}
]

Параграфы для анализа:
{paragraphs_text}
"""


def _build_batch_prompt(batch: list[ExtractedParagraph], start_index: int) -> str:
    """
    Форматирует батч параграфов в текстовое представление для LLM.

    Формат:
        [0] section="Название раздела": Текст параграфа
    """
    lines = []
    for i, p in enumerate(batch):
        section_info = ""
        if p.section_title:
            section_info = f'section="{p.section_title}"'
        flags = []
        if p.is_table_row:
            flags.append("table")
        if p.is_list_item:
            flags.append("list")
        flags_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"[{i}] {section_info}{flags_str}: {p.text}")

    return _ANALYSIS_USER_PROMPT_TEMPLATE.format(
        paragraphs_text="\n".join(lines)
    )


# ──────────────────────────────────────────────
# Response parsing
# ──────────────────────────────────────────────


def fallback_extract(text: str) -> list[Step]:
    """
    Минимальный fallback: детектирует паттерн «Должность + действие» через regex.

    Используется, если LLM вернула невалидный JSON.
    """
    steps: list[Step] = []
    text_clean = text.strip()

    # Паттерн 1: «Кто-то делает что-то» — именительный падеж + глагол
    # Например: "Начальник АЗС осуществляет приём ГСМ"
    patterns = [
        # Должность + глаголы действия: осуществляет, выполняет, производит, проводит и т.д.
        re.compile(
            r"([А-ЯЁ][а-яё]+(?:[- ][А-ЯЁ][а-яё]+)*)\s+"
            r"(?:осуществляет|выполняет|производит|проводит|составляет|оформляет|"
            r"передаёт|принимает|контролирует|подписывает|утверждает|ведёт|направляет|"
            r"предоставляет|готовит|согласовывает|разрабатывает|организует|обеспечивает)\s+"
            r"(.+)",
            re.IGNORECASE,
        ),
        # Должность + тире + действие: "Начальник АЗС — осуществляет приём"
        re.compile(
            r"([А-ЯЁ][а-яё]+(?:[- ][А-ЯЁ][а-яё]+)*)\s*[—–-]\s*(.+)",
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        m = pattern.search(text_clean)
        if m:
            role = m.group(1).strip()
            action = m.group(2).strip()
            # Обрезаем слишком длинные «действия» (это уже не действие, а целое предложение)
            if len(action) > 200:
                action = action[:200]
            steps.append(Step(role=role, action=action))
            break  # берём первое совпадение

    return steps


def _parse_llm_response(
    response_text: str,
    batch_indices: list[int],
) -> list[AnalyzedParagraph]:
    """
    Парсит ответ LLM и возвращает список AnalyzedParagraph для батча.

    Стратегия:
    1. Пробуем распарсить как JSON (из markdown-блока или чистый JSON)
    2. Если JSON невалиден — пробуем fallback_extract для каждого параграфа
    3. Если fallback тоже пустой — возвращаем пустые шаги

    Parameters
    ----------
    response_text : str
        Сырой текст ответа LLM.
    batch_indices : list[int]
        Индексы параграфов в батче (для сопоставления).

    Returns
    -------
    list[AnalyzedParagraph]
        Список результатов для каждого параграфа батча.
    """
    # Инициализируем пустыми результатами
    result_map: dict[int, AnalyzedParagraph] = {
        idx: AnalyzedParagraph(
            paragraph_index=idx,
            original_text="",
            section_title=None,
            is_table_row=False,
            is_list_item=False,
            steps=[],
        )
        for idx in batch_indices
    }

    # ── Шаг 1: пытаемся извлечь JSON из ответа ──
    json_data = try_extract_json(response_text)

    if json_data is not None and isinstance(json_data, list):
        # Успешно распарсили JSON-массив
        for entry in json_data:
            if not isinstance(entry, dict):
                continue
            idx = entry.get("paragraph_index")
            if idx is None or idx not in result_map:
                continue
            raw_steps = entry.get("steps", [])
            if not isinstance(raw_steps, list):
                continue
            steps = []
            for s in raw_steps:
                if isinstance(s, dict):
                    steps.append(
                        Step(
                            role=_safe_str(s.get("role")),
                            action=_safe_str(s.get("action")),
                            deadline=_safe_str(s.get("deadline")),
                            method=_safe_str(s.get("method")),
                            condition=_safe_str(s.get("condition")),
                            document=_safe_str(s.get("document")),
                            consequence=_safe_str(s.get("consequence")),
                        )
                    )
            if idx in result_map:
                result_map[idx].steps = steps

        return list(result_map.values())

    # ── Шаг 2: JSON не удался — пробуем fallback для КАЖДОГО параграфа ──
    logger.warning(
        "LLM response is not valid JSON, using fallback regex for %d paragraphs",
        len(batch_indices),
    )

    # Пытаемся найти шаги для каждого параграфа индивидуально
    for idx in batch_indices:
        ap = result_map[idx]
        if not ap.original_text:
            ap.parse_error = True
            continue
        steps = fallback_extract(ap.original_text)
        if steps:
            ap.steps = steps
        ap.parse_error = True

    return list(result_map.values())


# ──────────────────────────────────────────────
# Statistics
# ──────────────────────────────────────────────


def compute_stats(paragraphs: list[AnalyzedParagraph]) -> dict[str, Any]:
    """
    Вычисляет статистику по проанализированным параграфам.

    Returns
    -------
    dict со следующими ключами:
        - total_paragraphs
        - total_steps
        - paragraphs_with_role_pct
        - paragraphs_with_deadline_pct
        - paragraphs_with_method_pct
        - paragraphs_with_condition_pct
        - paragraphs_with_document_pct
        - paragraphs_with_consequence_pct
        - avg_steps_per_paragraph
        - parse_error_count
    """
    total = len(paragraphs)
    if total == 0:
        return {
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
        }

    total_steps = sum(len(p.steps) for p in paragraphs)
    parse_error_count = sum(1 for p in paragraphs if p.parse_error)

    def _any_field(field: str) -> int:
        return sum(
            1 for p in paragraphs if any(getattr(s, field) for s in p.steps)
        )

    return {
        "total_paragraphs": total,
        "total_steps": total_steps,
        "paragraphs_with_role_pct": round(
            _any_field("role") / total * 100, 1
        ),
        "paragraphs_with_deadline_pct": round(
            _any_field("deadline") / total * 100, 1
        ),
        "paragraphs_with_method_pct": round(
            _any_field("method") / total * 100, 1
        ),
        "paragraphs_with_condition_pct": round(
            _any_field("condition") / total * 100, 1
        ),
        "paragraphs_with_document_pct": round(
            _any_field("document") / total * 100, 1
        ),
        "paragraphs_with_consequence_pct": round(
            _any_field("consequence") / total * 100, 1
        ),
        "avg_steps_per_paragraph": round(total_steps / total, 2),
        "parse_error_count": parse_error_count,
    }


# ──────────────────────────────────────────────
# Main function
# ──────────────────────────────────────────────


async def analyze_paragraphs(
    paragraphs: list[ExtractedParagraph],
    provider: BaseLLMProvider,
    batch_size: int = 3,
    on_batch_complete: Optional[Callable[[int, int, list[AnalyzedParagraph]], Awaitable[None]]] = None,
) -> AnalysisResult:
    """
    Анализирует параграфы регламента с помощью LLM.

    Parameters
    ----------
    paragraphs : list[ExtractedParagraph]
        Список извлечённых параграфов (из paragraph_extractor).
    provider : BaseLLMProvider
        LLM-провайдер для генерации анализа.
    batch_size : int
        Размер батча для отправки LLM (по умолч. 3).

    Returns
    -------
    AnalysisResult
        Результат анализа со статистикой.
    """
    # ── Шаг 1: фильтрация ──
    # Берём только body-параграфы (не заголовки)
    body_paragraphs = [
        p for p in paragraphs if not p.is_heading
    ]

    if not body_paragraphs:
        logger.warning("No body paragraphs to analyze")
        return AnalysisResult(
            paragraphs=[],
            stats=compute_stats([]),
        )

    logger.info(
        "Analyzing %d body paragraphs (filtered from %d total)",
        len(body_paragraphs),
        len(paragraphs),
    )

    # ── Шаг 2: батчинг ──
    all_results: list[AnalyzedParagraph] = []
    total_batches = (len(body_paragraphs) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start = batch_num * batch_size
        end = min(start + batch_size, len(body_paragraphs))
        batch = body_paragraphs[start:end]
        batch_indices = [p.index for p in batch]
        batch_results: list[AnalyzedParagraph] = []

        logger.info(
            "Processing batch %d/%d (paragraphs %d–%d)",
            batch_num + 1,
            total_batches,
            batch_indices[0],
            batch_indices[-1],
        )

        # ── Шаг 3: формируем промпт ──
        prompt = _build_batch_prompt(batch, start)

        # ── Шаг 4: вызываем LLM с таймаутом 120с ──
        try:
            response = await asyncio.wait_for(
                provider.generate(
                    prompt=prompt,
                    system_prompt=_ANALYSIS_SYSTEM_PROMPT,
                    temperature=0.1,  # низкая температура для структурированного вывода
                    max_tokens=8192,
                ),
                timeout=120,  # 2 минуты на батч
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Batch %d/%d timed out after 120s — using fallback extraction",
                batch_num + 1,
                total_batches,
            )
            for p in batch:
                steps = fallback_extract(p.text)
                batch_results.append(
                    AnalyzedParagraph(
                        paragraph_index=p.index,
                        original_text=p.text,
                        section_title=p.section_title,
                        is_table_row=p.is_table_row,
                        is_list_item=p.is_list_item,
                        steps=steps,
                        parse_error=True,
                    )
                )
            all_results.extend(batch_results)
            if on_batch_complete:
                await on_batch_complete(batch_num + 1, total_batches, batch_results)
            continue
        except Exception as e:
            logger.error("LLM call failed for batch %d: %s", batch_num + 1, e)
            # При ошибке LLM возвращаем пустые шаги для всего батча
            for p in batch:
                batch_results.append(
                    AnalyzedParagraph(
                        paragraph_index=p.index,
                        original_text=p.text,
                        section_title=p.section_title,
                        is_table_row=p.is_table_row,
                        is_list_item=p.is_list_item,
                        steps=[],
                        parse_error=True,
                    )
                )
            all_results.extend(batch_results)
            if on_batch_complete:
                await on_batch_complete(batch_num + 1, total_batches, batch_results)
            continue

        # ── Шаг 5: парсим ответ ──
        parsed = _parse_llm_response(response, batch_indices)

        # Обогащаем parsed-данные из исходных параграфов
        parsed_map = {ap.paragraph_index: ap for ap in parsed}
        for p in batch:
            ap = parsed_map.get(p.index)
            if ap is not None:
                ap.original_text = p.text
                ap.section_title = p.section_title
                ap.is_table_row = p.is_table_row
                ap.is_list_item = p.is_list_item
            else:
                # Если парсер не вернул данных для параграфа
                batch_results.append(
                    AnalyzedParagraph(
                        paragraph_index=p.index,
                        original_text=p.text,
                        section_title=p.section_title,
                        is_table_row=p.is_table_row,
                        is_list_item=p.is_list_item,
                        steps=[],
                        parse_error=True,
                    )
                )
                continue
            batch_results.append(ap)

        all_results.extend(batch_results)
        if on_batch_complete:
            await on_batch_complete(batch_num + 1, total_batches, batch_results)

    # ── Шаг 6: вычисляем статистику ──
    stats = compute_stats(all_results)

    logger.info(
        "Analysis complete: %d paragraphs, %d steps, %.1f%% with role",
        stats["total_paragraphs"],
        stats["total_steps"],
        stats["paragraphs_with_role_pct"],
    )

    return AnalysisResult(
        paragraphs=all_results,
        stats=stats,
    )


# ──────────────────────────────────────────────
# Verification
# ──────────────────────────────────────────────


if __name__ == "__main__":
    import asyncio
    import sys

    async def test():
        from app.services.paragraph_extractor import extract_paragraphs
        from app.providers.ollama import OllamaProvider

        # Путь по умолчанию
        docx_path = r"E:\OCProj\Reglametns\Reglament GSM.docx"
        if len(sys.argv) > 1:
            docx_path = sys.argv[1]

        print(f"Extracting paragraphs from: {docx_path}")
        pars = extract_paragraphs(docx_path)
        body = [p for p in pars if not p.is_heading][:16]  # Первые 16 body = 2 батча
        print(f"Extracted {len(pars)} paragraphs total, using first {len(body)} body paragraphs")

        print(f"Creating Ollama provider...")
        provider = OllamaProvider()

        print(f"Starting analysis...")
        result = await analyze_paragraphs(body, provider)
        print(f"\n--- Results ---")
        print(f"Analyzed {len(result.paragraphs)} paragraphs")
        print(f"Total steps: {result.stats['total_steps']}")
        print(f"Stats: {result.stats}")

        # Показываем первые 3 параграфа с шагами
        shown = 0
        for ap in result.paragraphs:
            if ap.steps and shown < 3:
                print(f"\n  Paragraph [{ap.paragraph_index}]:")
                print(f"    Text: {ap.original_text[:100]}...")
                for i, s in enumerate(ap.steps):
                    print(f"    Step {i + 1}: role={s.role}, action={s.action}")
                    if s.deadline:
                        print(f"             deadline={s.deadline}")
                    if s.method:
                        print(f"             method={s.method}")
                shown += 1

        # Показываем статистику по ошибкам парсинга
        errors = sum(1 for ap in result.paragraphs if ap.parse_error)
        if errors:
            print(f"\n  [!] Parse errors: {errors} paragraphs")

        print("\n--- Done ---")

    asyncio.run(test())
