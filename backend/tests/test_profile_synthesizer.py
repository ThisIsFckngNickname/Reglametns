"""Tests for app.services.profile_synthesizer (pure functions only, no LLM)."""

from app.services.profile_synthesizer import (
    ParagraphLogicProfile,
    _collect_all_steps,
    _steps_to_json,
    _sample_steps,
    _merge_profile_data,
    validate_profile,
    statistical_fallback,
)
from app.services.paragraph_analyzer import Step, AnalyzedParagraph


class TestCollectAllSteps:
    def test_empty_input(self):
        assert _collect_all_steps([]) == []

    def test_single_paragraph(self):
        ap = AnalyzedParagraph(
            paragraph_index=0, original_text="text",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="Роль", action="Действие")],
        )
        steps = _collect_all_steps([(0, ap)])
        assert len(steps) == 1
        assert steps[0].role == "Роль"

    def test_multiple_paragraphs(self):
        ap1 = AnalyzedParagraph(
            paragraph_index=0, original_text="text1",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="Роль1", action="Действие1")],
        )
        ap2 = AnalyzedParagraph(
            paragraph_index=1, original_text="text2",
            section_title=None, is_table_row=False, is_list_item=False,
            steps=[Step(role="Роль2", action="Действие2")],
        )
        steps = _collect_all_steps([(0, ap1), (1, ap2)])
        assert len(steps) == 2


class TestStepsToJson:
    def test_empty_steps(self):
        assert _steps_to_json([]) == "[]"

    def test_step_with_all_fields(self):
        s = Step(role="Р", action="А", deadline="Д", method="М",
                 condition="У", document="Док", consequence="Посл")
        result = _steps_to_json([s])
        parsed = __import__("json").loads(result)
        assert len(parsed) == 1
        assert parsed[0]["role"] == "Р"
        assert parsed[0]["consequence"] == "Посл"

    def test_step_with_only_some_fields(self):
        s = Step(role="Роль", action="Действие")
        result = _steps_to_json([s])
        parsed = __import__("json").loads(result)
        assert len(parsed) == 1
        assert parsed[0]["role"] == "Роль"
        assert "deadline" not in parsed[0]


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


class TestMergeProfileData:
    def test_basic_merge(self):
        base = ParagraphLogicProfile(version=2)
        data = {
            "version": 2,
            "source_document_count": 3,
            "total_steps_analyzed": 150,
            "step_templates": ["[Роль] [действие]"],
            "vocabulary": {"roles": {"Начальник": 5}},
            "logic_rules": {"role_required": True},
            "section_patterns": {},
            "transition_patterns": [],
        }
        profile = _merge_profile_data(base, data, 3, 150)
        assert profile.source_document_count == 3
        assert profile.total_steps_analyzed == 150
        assert profile.step_templates == ["[Роль] [действие]"]

    def test_defaults_on_missing_data(self):
        base = ParagraphLogicProfile(version=2, step_templates=["default"])
        data = {}
        profile = _merge_profile_data(base, data, 1, 0)
        assert profile.step_templates == ["default"]


class TestValidateProfile:
    def test_valid_profile(self):
        profile = ParagraphLogicProfile(
            version=2,
            total_steps_analyzed=100,
            step_templates=["[Роль] [действие]"],
            vocabulary={"roles": {"Начальник": 5}, "actions": {"делает": 10}},
            logic_rules={"role_required": True},
        )
        assert validate_profile(profile) == []

    def test_empty_templates_warning(self):
        profile = ParagraphLogicProfile(version=2, total_steps_analyzed=100)
        warnings = validate_profile(profile)
        assert any("No step templates" in w for w in warnings)

    def test_no_roles_warning(self):
        profile = ParagraphLogicProfile(
            version=2, total_steps_analyzed=100,
            step_templates=["test"],
            vocabulary={},
            logic_rules={"role_required": True},
        )
        warnings = validate_profile(profile)
        assert any("No roles" in w for w in warnings)

    def test_zero_steps_warning(self):
        profile = ParagraphLogicProfile(
            version=2, total_steps_analyzed=0,
            step_templates=["test"],
            vocabulary={"roles": {"Р": 1}, "actions": {"Д": 1}},
            logic_rules={"role_required": True},
        )
        warnings = validate_profile(profile)
        assert any("total_steps_analyzed" in w for w in warnings)


class TestStatisticalFallback:
    def test_empty_steps(self):
        profile = statistical_fallback([])
        assert profile.total_steps_analyzed == 0
        assert profile.step_templates == ["[Должность] [действие]"]

    def test_with_role_steps(self):
        steps = [Step(role="Начальник", action="делает")]
        profile = statistical_fallback(steps)
        assert profile.total_steps_analyzed == 1
        assert profile.vocabulary["roles"] == {"Начальник": 1}
        assert profile.vocabulary["actions"] == {"делает": 1}
        assert profile.logic_rules["role_required"] is True

    def test_with_deadline(self):
        steps = [Step(role="Р", action="Д", deadline="ежедневно")]
        profile = statistical_fallback(steps)
        assert "ежедневно" in profile.vocabulary["deadlines"]
        assert profile.logic_rules["deadline_required"] is True

    def test_with_all_fields(self):
        steps = [Step(
            role="Р", action="Д", deadline="Д", method="М",
            condition="У", document="Док", consequence="Посл",
        )]
        profile = statistical_fallback(steps)
        assert profile.logic_rules["conditional_logic"] is True
        assert profile.logic_rules["has_consequences"] is True
        assert len(profile.step_templates) == 5  # All template variants generated
