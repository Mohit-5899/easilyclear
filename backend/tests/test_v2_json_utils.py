"""Tests for the shared JSON-extraction helper used by V2 LLM modules."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_v2._json_utils import ensure_valid_json


def test_bare_json_object_parses_unchanged():
    src = '{"a": 1, "b": "x"}'
    assert ensure_valid_json(src) == src


def test_fenced_json_strips_fences():
    src = '```json\n{"a": 1}\n```'
    assert ensure_valid_json(src) == '{"a": 1}'


def test_unfenced_json_with_language_marker_strips_fences():
    src = '```\n{"a": 1}\n```'
    assert ensure_valid_json(src) == '{"a": 1}'


def test_prose_prefixed_json_extracts_object():
    src = 'Sure thing! Here is the JSON you asked for:\n{"a": 1, "nested": {"b": 2}}'
    out = ensure_valid_json(src)
    assert out == '{"a": 1, "nested": {"b": 2}}'


def test_empty_response_raises_value_error():
    with pytest.raises(ValueError, match="empty"):
        ensure_valid_json("")


def test_no_braces_raises_value_error():
    with pytest.raises(ValueError, match="no JSON object"):
        ensure_valid_json("just some prose without any json")


def test_unbalanced_braces_raises_value_error():
    with pytest.raises(ValueError):
        ensure_valid_json('{"a": 1, "b":')
