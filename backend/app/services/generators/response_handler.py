"""
Response handler — parse LLM responses, format style patterns, manage output paths.
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional

from app.core.exceptions import BadRequestException
MOCK_RESPONSE = {
    "title": "Регламент взаимодействия (демо-режим)",
    "description": "Документ создан в демо-режиме без подключения к LLM. Настройте Ollama или GigaChat для реальной генерации.",
    "sections": [
        {
            "title": "1. Общие положения",
            "level": 1,
            "content": "1.1. Настоящий Регламент определяет порядок взаимодействия между подразделениями Холдинга.\n1.2. Документ разработан в соответствии с действующим законодательством РФ.",
            "subsections": [
                {
                    "title": "1.1. Цели и задачи",
                    "level": 2,
                    "content": "Основной целью настоящего Регламента является обеспечение эффективного взаимодействия между структурными подразделениями."
                }
            ]
        },
        {
            "title": "2. Порядок взаимодействия",
            "level": 1,
            "content": "2.1. Взаимодействие между подразделениями осуществляется в соответствии с утверждёнными бизнес-процессами.",
            "subsections": []
        }
    ],
    "terms": [
        {"term": "Холдинг", "definition": "Группа взаимосвязанных организаций"},
        {"term": "Регламент", "definition": "Документ, устанавливающий порядок взаимодействия"}
    ],
    "abbreviations": [
        {"abbreviation": "ООО", "full_form": "Общество с ограниченной ответственностью"}
    ],
    "references": [
        {"title": "Гражданский кодекс РФ", "source": "КонсультантПлюс"}
    ]
}

logger = logging.getLogger(__name__)


class ResponseHandler:
    """Handles LLM response parsing and formatting."""

    async def parse_response(self, raw_response: str) -> dict:
        """Parse LLM response with fallback for malformed JSON.

        Strategy:
        1. Try json.loads() directly
        2. If fails, try to extract JSON from markdown code block (```json ... ```)
        3. If still fails, try to find JSON-like structure in the text
        4. If all fail, raise BadRequestException
        """
        if not raw_response or not raw_response.strip():
            logger.warning("Empty response from LLM, returning mock response")
            return dict(MOCK_RESPONSE)

        # Strategy 1: Direct parse
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract from markdown code block
        json_match = re.search(
            r"```(?:json)?\s*([\s\S]*?)```", raw_response, re.IGNORECASE
        )
        if json_match:
            extracted = json_match.group(1).strip()
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

        # Strategy 3: Try to find JSON-like structure in the text
        json_match = re.search(r"(\{[\s\S]*\})", raw_response)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                logger.warning(
                    f"Found JSON-like structure but failed to parse. "
                    f"Extracted: {json_match.group(1)[:200]}"
                )

        logger.error(f"Failed to parse LLM response as JSON: {raw_response[:500]}")
        raise BadRequestException(
            code="GENERATION_FAILED",
            message="Не удалось обработать ответ от LLM. Попробуйте снова.",
        )

    def format_style_patterns_for_prompt(self, style_settings: Optional[dict]) -> str:
        """Format style settings into prompt-friendly string."""
        if not style_settings or not isinstance(style_settings, dict):
            return ""

        lines = []
        typical_phrases = style_settings.get("typical_phrases", [])
        if typical_phrases and isinstance(typical_phrases, list):
            phrases_str = "; ".join(f"«{p}…»" for p in typical_phrases[:5])
            lines.append(f"Типичные фразы: {phrases_str}")

        avg_len = style_settings.get("avg_sentence_length")
        if avg_len:
            lines.append(f"Средняя длина предложения: ~{avg_len} слов.")

        return " | ".join(lines)

    def get_output_path(self, company_id: int, title: str) -> str:
        """Generate output path for the generated .docx file.

        Returns a path in the system temp directory.
        """
        safe_title = re.sub(r"[^\w\s-]", "", title).strip()[:50]
        safe_title = safe_title.replace(" ", "_")
        timestamp = int(datetime.now(timezone.utc).timestamp())
        filename = f"generated_{company_id}_{safe_title}_{timestamp}.docx"
        output_dir = os.path.join(tempfile.gettempdir(), "srp_generated")
        os.makedirs(output_dir, exist_ok=True)
        return os.path.join(output_dir, filename)

    def get_mock_response(self) -> dict:
        """Return a copy of the mock response data."""
        return dict(MOCK_RESPONSE)


# Singleton
response_handler = ResponseHandler()
