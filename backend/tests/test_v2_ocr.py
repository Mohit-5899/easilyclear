"""Tests for the OCR / native-text merge helper (spec Addendum A.10)."""

from __future__ import annotations

import sys
from pathlib import Path

# Make backend/ importable regardless of CWD.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from ingestion_v2.ocr import merge_ocr_with_native


def test_empty_ocr_returns_native_unchanged():
    native = "Native text body."
    assert merge_ocr_with_native(native, "") == native


def test_ocr_fully_duplicating_native_adds_nothing():
    native = "The capital of Rajasthan is Jaipur.\nGurushikhar is in Sirohi."
    ocr = "the capital of rajasthan is jaipur\ngurushikhar is in sirohi"
    merged = merge_ocr_with_native(native, ocr)
    assert merged == native


def test_ocr_only_lines_are_appended():
    native = "Body paragraph one."
    ocr = "Body paragraph one.\nMap label: Thar Desert\nDistrict: Jaisalmer"
    merged = merge_ocr_with_native(native, ocr)
    assert "Map label: Thar Desert" in merged
    assert "District: Jaisalmer" in merged
    # original native still present
    assert "Body paragraph one." in merged


def test_short_ocr_lines_are_dropped():
    """Lines shorter than 4 chars (after normalize) are noise, dropped."""
    native = "Real content."
    ocr = "x\n.\n  \nKept this longer label"
    merged = merge_ocr_with_native(native, ocr)
    assert "Kept this longer label" in merged
    assert "x\n" not in merged.replace(native, "")


def test_duplicate_ocr_lines_are_deduped():
    native = "Body."
    ocr = "Aravalli Range\nAravalli Range\nARAVALLI RANGE"
    merged = merge_ocr_with_native(native, ocr)
    # First form preserved; subsequent normalized-equal forms dropped.
    assert merged.count("Aravalli Range") + merged.count("ARAVALLI RANGE") == 1
