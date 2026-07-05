"""Tests for app.services.insight_generator (pure functions only, no LLM)."""

from app.services.insight_generator import (
    DocumentInsights,
    _collect_steps,
    _steps_to_json,
    _sample_steps,
    _statistical_analysis,
)
from app.services.paragraph_analyzer import Step, AnalyzedParagraph
import json


class TestCollectSteps:
    def test_empty_input(self):
        assert _collect_steps([]) == []

    def test_single_paragraph(self):
        ap = AnalyzedParagraph(
            paragraph_index=0, original_text="text",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="\u0420\u043e\u043b\u044c", action="\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435")],
        )
        steps = _collect_steps([ap])
        assert len(steps) == 1
        assert steps[0].role == "\u0420\u043e\u043b\u044c"

    def test_multiple_paragraphs(self):
        ap1 = AnalyzedParagraph(
            paragraph_index=0, original_text="text1",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="\u0420\u043e\u043b\u044c1", action="\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u04351")],
        )
        ap2 = AnalyzedParagraph(
            paragraph_index=1, original_text="text2",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="\u0420\u043e\u043b\u044c2", action="\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u04352")],
        )
        steps = _collect_steps([ap1, ap2])
        assert len(steps) == 2

    def test_paragraph_with_no_steps(self):
        ap = AnalyzedParagraph(
            paragraph_index=0, original_text="text",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[],
        )
        assert _collect_steps([ap]) == []


class TestStepsToJson:
    def test_empty_steps(self):
        assert _steps_to_json([]) == "[]"

    def test_step_with_all_fields(self):
        s = Step(role="\u0420", action="\u0410", deadline="\u0414", method="\u041c",
                 condition="\u0423", document="\u0414\u043e\u043a", consequence="\u041f\u043e\u0441\u043b")
        result = _steps_to_json([s])
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["role"] == "\u0420"
        assert parsed[0]["consequence"] == "\u041f\u043e\u0441\u043b"

    def test_step_with_only_some_fields(self):
        s = Step(role="\u0420\u043e\u043b\u044c", action="\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435")
        result = _steps_to_json([s])
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["role"] == "\u0420\u043e\u043b\u044c"
        assert "deadline" not in parsed[0]

    def test_excludes_none_fields(self):
        """\u041f\u043e\u043b\u044f \u0441 None \u043d\u0435 \u0434\u043e\u043b\u0436\u043d\u044b \u043f\u043e\u043f\u0430\u0434\u0430\u0442\u044c \u0432 JSON."""
        s = Step(role="\u0420\u043e\u043b\u044c", action="\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435", deadline=None, method=None)
        result = _steps_to_json([s])
        parsed = json.loads(result)
        assert "deadline" not in parsed[0]
        assert "method" not in parsed[0]


class TestSampleSteps:
    def test_under_limit_returns_all(self):
        steps = [Step() for _ in range(100)]
        result = _sample_steps(steps, max_steps=500)
        assert len(result) == 100

    def test_at_limit_returns_all(self):
        steps = [Step() for _ in range(500)]
        result = _sample_steps(steps, max_steps=500)
        assert len(result) == 500

    def test_over_limit_sampling(self):
        steps = [Step(action=f"Action {i}") for i in range(600)]
        result = _sample_steps(steps, max_steps=500)
        assert len(result) == 500
        # First 250 should be preserved
        assert result[0].action == "Action 0"
        assert result[249].action == "Action 249"

    def test_exact_limit(self):
        steps = [Step() for _ in range(500)]
        result = _sample_steps(steps)
        assert len(result) == 500


class TestStatisticalAnalysis:
    def test_empty_steps(self):
        result = _statistical_analysis([])
        assert isinstance(result, dict)
        assert "step_templates" in result
        assert "vocabulary" in result
        assert "logic_rules" in result
        assert result["step_templates"] == ["[\u0414\u043e\u043b\u0436\u043d\u043e\u0441\u0442\u044c] [\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435]"]

    def test_with_role_steps(self):
        steps = [Step(role="\u041d\u0430\u0447\u0430\u043b\u044c\u043d\u0438\u043a", action="\u0434\u0435\u043b\u0430\u0435\u0442")]
        result = _statistical_analysis(steps)
        assert result["vocabulary"]["roles"] == {"\u041d\u0430\u0447\u0430\u043b\u044c\u043d\u0438\u043a": 1}
        assert result["vocabulary"]["actions"] == {"\u0434\u0435\u043b\u0430\u0435\u0442": 1}
        assert result["logic_rules"]["role_required"] is True

    def test_with_deadline(self):
        steps = [Step(role="\u0420", action="\u0414", deadline="\u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u043e")]
        result = _statistical_analysis(steps)
        assert "\u0435\u0436\u0435\u0434\u043d\u0435\u0432\u043d\u043e" in result["vocabulary"]["deadlines"]
        assert result["logic_rules"]["deadline_required"] is True

    def test_with_all_fields(self):
        steps = [Step(
            role="\u0420", action="\u0414", deadline="\u0414", method="\u041c",
            condition="\u0423", document="\u0414\u043e\u043a", consequence="\u041f\u043e\u0441\u043b",
        )]
        result = _statistical_analysis(steps)
        assert result["logic_rules"]["conditional_logic"] is True
        assert result["logic_rules"]["has_consequences"] is True
        # Should have at least the base template
        assert len(result["step_templates"]) >= 1

    def test_with_condition(self):
        steps = [Step(role="\u0420", action="\u0414", condition="\u043f\u0440\u0438 \u0430\u0432\u0430\u0440\u0438\u0438")]
        result = _statistical_analysis(steps)
        assert result["logic_rules"]["conditional_logic"] is True
        assert "\u043f\u0440\u0438 \u0430\u0432\u0430\u0440\u0438\u0438" in result["vocabulary"]["conditions"]


class TestDocumentInsights:
    def test_default_construction(self):
        insights = DocumentInsights()
        assert insights.version == 2
        assert insights.total_paragraphs == 0
        assert insights.total_steps == 0
        assert insights.step_templates == []
        assert insights.vocabulary == {}
        assert insights.logic_rules == {}

    def test_custom_construction(self):
        insights = DocumentInsights(
            version=2,
            total_paragraphs=5,
            total_steps=20,
            step_templates=["[\u0420\u043e\u043b\u044c] [\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435]"],
            vocabulary={"roles": {"\u041d\u0430\u0447\u0430\u043b\u044c\u043d\u0438\u043a": 5}},
            logic_rules={"role_required": True},
        )
        assert insights.total_paragraphs == 5
        assert insights.total_steps == 20
        assert insights.step_templates == ["[\u0420\u043e\u043b\u044c] [\u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0435]"]
        assert insights.vocabulary["roles"] == {"\u041d\u0430\u0447\u0430\u043b\u044c\u043d\u0438\u043a": 5}
