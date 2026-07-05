"""Shared test fixtures."""

import pytest
from app.services.paragraph_extractor import ExtractedParagraph
from app.services.paragraph_analyzer import Step, AnalyzedParagraph


@pytest.fixture
def sample_step() -> Step:
    return Step(
        role="Начальник АЗС",
        action="осуществляет приём ГСМ",
        deadline="ежедневно до 10:00",
        method="в системе 1С:Предприятие",
    )


@pytest.fixture
def sample_paragraph() -> ExtractedParagraph:
    return ExtractedParagraph(
        index=0,
        text="Начальник АЗС осуществляет приём ГСМ ежедневно до 10:00 в системе 1С:Предприятие",
        section_title="Общие положения",
        is_heading=False,
        is_table_row=False,
        is_list_item=False,
        heading_level=0,
        char_count=77,
    )


@pytest.fixture
def sample_analyzed_paragraph(sample_step) -> AnalyzedParagraph:
    return AnalyzedParagraph(
        paragraph_index=0,
        original_text="Начальник АЗС осуществляет приём ГСМ ежедневно до 10:00",
        section_title="Общие положения",
        is_table_row=False,
        is_list_item=False,
        steps=[sample_step],
    )


@pytest.fixture
def sample_heading_paragraph() -> ExtractedParagraph:
    return ExtractedParagraph(
        index=5,
        text="1. Общие положения",
        section_title=None,
        is_heading=True,
        is_table_row=False,
        is_list_item=False,
        heading_level=1,
        char_count=17,
    )
