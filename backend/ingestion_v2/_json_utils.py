"""Shared JSON-extraction helper for V2 LLM responses.

Models occasionally wrap JSON in ```json fences or prepend a sentence even
when asked not to. This helper pulls out the first balanced ``{...}`` block
and returns it as a parseable string.
"""

from __future__ import annotations

import json
import re


_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def ensure_valid_json(text: str) -> str:
    """Strip markdown fences / prose around a JSON object.

    Raises:
        ValueError: if no parseable JSON object is found.
    """
    if not text:
        raise ValueError("empty model response")

    stripped = text.strip()
    fence = _FENCE_RE.match(stripped)
    if fence:
        stripped = fence.group(1).strip()

    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start == -1:
        raise ValueError("no JSON object found in model response")
    depth = 0
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = stripped[start : idx + 1]
                json.loads(candidate)
                return candidate
    raise ValueError("unbalanced braces in model response")
