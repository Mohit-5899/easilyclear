"""Quick chat-quality eval harness — hits /tutor/agent_chat with a battery
of representative questions and reports per-question:

  - tool calls fired (agentic behavior check)
  - citations streamed (groundedness check)
  - brand-strip violations (compliance check — no Springboard / Academy / RBSE / NCERT)
  - first-token latency + total latency
  - response text (truncated)

Run after the backend is up on http://127.0.0.1:8010 with LLM_PROVIDER=openrouter.

    uv run python scripts/eval_chat.py
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


BACKEND = "http://127.0.0.1:8010"
BRAND_TOKENS = ["Springboard", "Academy", "RBSE", "NCERT", "Vedantu", "Utkarsh", "Drishti"]


@dataclass
class TurnReport:
    question: str
    scope: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    first_token_s: float | None = None
    total_s: float = 0.0
    error: str | None = None

    @property
    def brand_violations(self) -> list[str]:
        hay = self.answer
        for c in self.citations:
            hay += " " + json.dumps(c)
        return [b for b in BRAND_TOKENS if b in hay]


def _stream(question: str, scope: str = "all") -> TurnReport:
    rep = TurnReport(question=question, scope=scope)
    payload = {
        "messages": [{"role": "user", "content": question}],
        "default_scope": scope,
        "max_steps": 3,
    }
    started = time.perf_counter()
    try:
        with httpx.stream(
            "POST", f"{BACKEND}/tutor/agent_chat",
            json=payload, timeout=httpx.Timeout(60.0, read=60.0),
            headers={"Content-Type": "application/json"},
        ) as r:
            if r.status_code != 200:
                rep.error = f"HTTP {r.status_code}: {r.text[:200]}"
                return rep
            buffer = ""
            for chunk in r.iter_text():
                buffer += chunk
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    if not frame.startswith("data: "):
                        continue
                    payload_str = frame[6:].strip()
                    if not payload_str or payload_str == "[DONE]":
                        continue
                    try:
                        ev = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    t = ev.get("type", "")
                    if t == "tool-call":
                        rep.tool_calls.append(ev)
                    elif t == "tool-result":
                        rep.tool_results.append(ev)
                    elif t == "data-citation":
                        rep.citations.append(ev.get("data", {}))
                    elif t == "text-delta":
                        if rep.first_token_s is None:
                            rep.first_token_s = time.perf_counter() - started
                        rep.answer += ev.get("delta", "")
    except httpx.HTTPError as e:
        rep.error = f"transport: {e}"
    rep.total_s = time.perf_counter() - started
    return rep


CASES: list[tuple[str, str]] = [
    # (question, scope)
    ("What is Mawath rainfall?", "subject"),
    ("Why is Aravalli called the planning region of Rajasthan?", "subject"),
    ("Name the highest peak of Aravalli with its district.", "subject"),
    ("Which districts have arid climate per Koppen classification?", "subject"),
    ("What is photosynthesis?", "subject"),  # out-of-source: agent should refuse / cite nothing
    ("Quote a paragraph about the Thar Desert.", "subject"),
    ("Which textbook are these notes from?", "subject"),  # brand-strip stress
]


def _fmt_pct(num: int, denom: int) -> str:
    if denom == 0:
        return "n/a"
    return f"{num}/{denom} ({100 * num // denom}%)"


def main() -> int:
    print(f"Eval against {BACKEND}  ·  {len(CASES)} cases\n")
    rows: list[TurnReport] = []
    for q, scope in CASES:
        print(f"  > [{scope}] {q[:70]}")
        rep = _stream(q, scope=scope)
        rows.append(rep)
        if rep.error:
            print(f"      ERROR: {rep.error}")
            continue
        print(
            f"      tools={len(rep.tool_calls)}  "
            f"cites={len(rep.citations)}  "
            f"first={rep.first_token_s:.1f}s  total={rep.total_s:.1f}s  "
            f"brand_leaks={len(rep.brand_violations)}"
        )
    print()

    # Aggregate
    n = len(rows)
    used_tool = sum(1 for r in rows if r.tool_calls)
    cited = sum(1 for r in rows if r.citations)
    brand_clean = sum(1 for r in rows if not r.brand_violations)
    errors = sum(1 for r in rows if r.error)
    avg_first = sum(r.first_token_s for r in rows if r.first_token_s) / max(1, sum(1 for r in rows if r.first_token_s))
    avg_total = sum(r.total_s for r in rows) / n

    print("=" * 70)
    print("CHAT QUALITY SUMMARY")
    print("=" * 70)
    print(f"  Tool-call rate       : {_fmt_pct(used_tool, n)}")
    print(f"  Citation rate        : {_fmt_pct(cited, n)}")
    print(f"  Brand-strip clean    : {_fmt_pct(brand_clean, n)}")
    print(f"  Errors               : {errors}")
    print(f"  Avg first-token      : {avg_first:.2f}s")
    print(f"  Avg total response   : {avg_total:.2f}s")
    print()

    # Per-case detail
    for i, r in enumerate(rows, 1):
        print(f"--- [{i}] {r.question} ---")
        if r.error:
            print(f"  ERROR: {r.error}")
            continue
        for c in r.tool_calls:
            args = c.get("args", {})
            print(f"  tool-call  scope={args.get('scope')}  q={(args.get('query') or '')[:50]}")
        for c in r.citations[:3]:
            print(f"  cite [{c.get('index')}]  page={c.get('page')}  {(c.get('snippet') or '')[:80]}")
        if len(r.citations) > 3:
            print(f"  ...{len(r.citations) - 3} more citations")
        print(f"  answer: {r.answer[:240]}{'…' if len(r.answer) > 240 else ''}")
        if r.brand_violations:
            print(f"  ⚠️  BRAND LEAK: {r.brand_violations}")
        print()

    # Exit non-zero if any case errored or leaked brand
    return 0 if errors == 0 and brand_clean == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
