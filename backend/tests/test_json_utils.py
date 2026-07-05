"""Tests for app.utils.json_utils."""

import json
from app.utils.json_utils import (
    try_extract_json,
    try_extract_json_array,
    try_extract_json_object,
    safe_str,
)


class TestTryExtractJsonArray:
    def test_pure_json_array(self):
        text = '[{"paragraph_index": 0, "steps": []}]'
        result = try_extract_json_array(text)
        assert result == [{"paragraph_index": 0, "steps": []}]

    def test_json_in_code_block(self):
        text = '```json\n[{"key": "value"}]\n```'
        result = try_extract_json_array(text)
        assert result == [{"key": "value"}]

    def test_json_in_code_block_no_lang(self):
        text = '```\n[{"key": "value"}]\n```'
        result = try_extract_json_array(text)
        assert result == [{"key": "value"}]

    def test_with_surrounding_text(self):
        text = 'Some text before\n```json\n[{"a": 1}]\n```\nSome text after'
        result = try_extract_json_array(text)
        assert result == [{"a": 1}]

    def test_balanced_bracket_extraction(self):
        text = 'Here is the result: [{"nested": {"inner": [1,2,3]}}] and that is all.'
        result = try_extract_json_array(text)
        assert result == [{"nested": {"inner": [1, 2, 3]}}]

    def test_invalid_json_returns_none(self):
        text = "This is not JSON at all"
        result = try_extract_json_array(text)
        assert result is None

    def test_empty_string_returns_none(self):
        assert try_extract_json_array("") is None


class TestTryExtractJsonObject:
    def test_pure_json_object(self):
        text = '{"version": 2, "total_steps_analyzed": 100}'
        result = try_extract_json_object(text)
        assert result == {"version": 2, "total_steps_analyzed": 100}

    def test_object_in_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = try_extract_json_object(text)
        assert result == {"key": "value"}

    def test_with_surrounding_text(self):
        text = 'Explanation:\n```\n{"a": 1}\n```\nThat is all.'
        result = try_extract_json_object(text)
        assert result == {"a": 1}

    def test_balanced_bracket_object(self):
        text = 'Result: {"nested": {"inner": [1,2,3]}} End.'
        result = try_extract_json_object(text)
        assert result == {"nested": {"inner": [1, 2, 3]}}

    def test_invalid_json_returns_none(self):
        assert try_extract_json_object("{{{broken") is None


class TestTryExtractJson:
    def test_array_is_preferred(self):
        text = '[{"a": 1}]'
        result = try_extract_json(text)
        assert result == [{"a": 1}]

    def test_object_fallback(self):
        text = '{"b": 2}'
        result = try_extract_json(text)
        assert result == {"b": 2}

    def test_none_for_invalid(self):
        assert try_extract_json("garbage") is None


class TestSafeStr:
    def test_none_returns_none(self):
        assert safe_str(None) is None

    def test_string_stripped(self):
        assert safe_str("  hello  ") == "hello"

    def test_empty_string_returns_none(self):
        assert safe_str("") is None

    def test_whitespace_only_returns_none(self):
        assert safe_str("   ") is None

    def test_int_converted(self):
        assert safe_str(42) == "42"

    def test_float_converted(self):
        assert safe_str(3.14) == "3.14"
