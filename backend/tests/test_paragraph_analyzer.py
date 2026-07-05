"""Tests for app.services.paragraph_analyzer (pure functions only, no LLM)."""

import json
from app.services.paragraph_analyzer import (
    Step,
    AnalyzedParagraph,
    AnalysisResult,
    compute_stats,
    fallback_extract,
    _build_batch_prompt,
    _safe_str,
)


class TestStep:
    def test_default_construction(self):
        s = Step()
        assert s.role is None
        assert s.action is None
        assert s.deadline is None
        assert s.method is None
        assert s.condition is None
        assert s.document is None
        assert s.consequence is None

    def test_full_construction(self):
        s = Step(
            role="Начальник АЗС",
            action="осуществляет приём",
            deadline="ежедневно до 10:00",
            method="1С",
            condition="при отклонении",
            document="акт",
            consequence="ответственность",
        )
        assert s.role == "Начальник АЗС"
        assert s.action == "осуществляет приём"
        assert s.deadline == "ежедневно до 10:00"

    def test_partial_construction(self):
        s = Step(role="Бухгалтер", action="составляет отчёт")
        assert s.role == "Бухгалтер"
        assert s.action == "составляет отчёт"
        assert s.deadline is None


class TestFallbackExtract:
    def test_simple_role_action(self):
        steps = fallback_extract("Начальник АЗС осуществляет приём ГСМ")
        assert len(steps) == 1
        assert steps[0].role == "Начальник АЗС"
        assert steps[0].action == "приём ГСМ"

    def test_role_with_dash(self):
        steps = fallback_extract("Начальник АЗС — осуществляет приём ГСМ")
        assert len(steps) == 1
        assert steps[0].role is not None
        assert steps[0].action is not None

    def test_multiple_verbs(self):
        text = "Главный бухгалтер составляет отчёт и передаёт его руководителю"
        steps = fallback_extract(text)
        assert len(steps) >= 1
        assert steps[0].role == "Главный бухгалтер"

    def test_no_match_returns_empty(self):
        steps = fallback_extract("Общие положения")
        assert len(steps) == 0

    def test_empty_string(self):
        assert fallback_extract("") == []

    def test_long_action_truncated(self):
        text = "Начальник АЗС осуществляет " + "очень длинное действие " * 20
        steps = fallback_extract(text)
        assert len(steps) == 1
        assert len(steps[0].action) <= 200

    def test_full_name_role(self):
        steps = fallback_extract("Заместитель начальника отдела контролирует выполнение")
        assert len(steps) == 1
        assert "Заместитель" in steps[0].role

    def test_verb_provides(self):
        steps = fallback_extract("Секретарь предоставляет отчёт ежемесячно")
        assert len(steps) == 1
        assert "отчёт" in steps[0].action


class TestBuildBatchPrompt:
    def test_basic_formatting(self):
        from app.services.paragraph_extractor import ExtractedParagraph

        paragraphs = [
            ExtractedParagraph(
                index=0, text="Первый параграф", section_title="Раздел 1",
                is_heading=False, is_table_row=False, is_list_item=False,
                heading_level=0, char_count=14,
            ),
            ExtractedParagraph(
                index=1, text="Второй параграф", section_title="Раздел 1",
                is_heading=False, is_table_row=True, is_list_item=False,
                heading_level=0, char_count=14,
            ),
        ]
        prompt = _build_batch_prompt(paragraphs, 0)
        assert "[0]" in prompt
        assert 'section="Раздел 1"' in prompt
        assert "Первый параграф" in prompt
        assert "Второй параграф" in prompt
        assert "table" in prompt

    def test_empty_batch(self):
        prompt = _build_batch_prompt([], 0)
        assert "Параграфы для анализа:" in prompt

    def test_list_flag(self):
        from app.services.paragraph_extractor import ExtractedParagraph

        paragraphs = [
            ExtractedParagraph(
                index=0, text="Элемент списка", section_title=None,
                is_heading=False, is_table_row=False, is_list_item=True,
                heading_level=0, char_count=14,
            ),
        ]
        prompt = _build_batch_prompt(paragraphs, 0)
        assert "list" in prompt


class TestComputeStats:
    def test_empty_paragraphs(self):
        stats = compute_stats([])
        assert stats["total_paragraphs"] == 0
        assert stats["total_steps"] == 0
        assert stats["parse_error_count"] == 0

    def test_single_paragraph_no_steps(self):
        paragraphs = [AnalyzedParagraph(
            paragraph_index=0, original_text="text",
            section_title=None, is_table_row=False, is_list_item=False,
        )]
        stats = compute_stats(paragraphs)
        assert stats["total_paragraphs"] == 1
        assert stats["total_steps"] == 0
        assert stats["paragraphs_with_role_pct"] == 0.0

    def test_paragraph_with_steps(self):
        paragraphs = [AnalyzedParagraph(
            paragraph_index=0, original_text="text",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="Роль", action="Действие")],
        )]
        stats = compute_stats(paragraphs)
        assert stats["total_paragraphs"] == 1
        assert stats["total_steps"] == 1
        assert stats["paragraphs_with_role_pct"] == 100.0

    def test_percentage_calculation(self):
        paragraphs = [
            AnalyzedParagraph(
                paragraph_index=i, original_text="text",
                section_title=None, is_table_row=False, is_list_item=False,
                steps=[Step(role="Роль" if i == 0 else None, action="Действие")],
            )
            for i in range(4)
        ]
        stats = compute_stats(paragraphs)
        assert stats["total_paragraphs"] == 4
        assert stats["total_steps"] == 4
        assert stats["paragraphs_with_role_pct"] == 25.0

    def test_parse_error_counted(self):
        paragraphs = [
            AnalyzedParagraph(
                paragraph_index=i, original_text="text",
                section_title=None, is_table_row=False, is_list_item=False,
                steps=[Step(role="Роль", action="Действие")],
                parse_error=(i == 0),
            )
            for i in range(5)
        ]
        stats = compute_stats(paragraphs)
        assert stats["parse_error_count"] == 1


class TestSafeStr:
    def test_none(self):
        assert _safe_str(None) is None

    def test_whitespace(self):
        assert _safe_str("  ") is None

    def test_stripped(self):
        assert _safe_str("  hello  ") == "hello"

    def test_int(self):
        assert _safe_str(42) == "42"
