"""
json_utils — shared JSON extraction utilities for LLM response parsing.
"""

import json
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def try_extract_json_array(text: str) -> Optional[list]:
    """
    Extract JSON array from LLM response text.
    Supports: ```json [...] ```, ``` [...] ```, pure [...] JSON, balanced bracket detection.
    """
    # Try json code block
    block_pattern = re.compile(
        r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", re.IGNORECASE
    )
    for match in block_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Pure JSON array
    text_stripped = text.strip()
    if text_stripped.startswith("["):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass

    # Balanced bracket search
    start_idx = text.find("[")
    if start_idx != -1:
        depth = 0
        for i, ch in enumerate(text[start_idx:], start=start_idx):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start_idx : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def try_extract_json_object(text: str) -> Optional[dict]:
    """
    Extract JSON object from LLM response text.
    Supports: ```json { ... } ```, ``` { ... } ```, pure { ... } JSON, balanced bracket detection.
    """
    # Try json code block
    block_pattern = re.compile(
        r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE
    )
    for match in block_pattern.finditer(text):
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Pure JSON object
    text_stripped = text.strip()
    if text_stripped.startswith("{"):
        try:
            return json.loads(text_stripped)
        except json.JSONDecodeError:
            pass

    # Balanced bracket search
    start_idx = text.find("{")
    if start_idx != -1:
        depth = 0
        for i, ch in enumerate(text[start_idx:], start=start_idx):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start_idx : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def try_extract_json(text: str) -> Any:
    """
    Universal JSON extraction — tries array first, then object.
    Returns parsed JSON or None.
    """
    result = try_extract_json_array(text)
    if result is not None:
        return result
    return try_extract_json_object(text)


def safe_str(value: Any) -> Optional[str]:
    """Safely convert value to string or return None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return str(value).strip() or None
