"""Smoke tests for the vendored PageIndex fork.

These verify the edits documented in ARCHITECTURE.md §11 — the LLMClient
injection point, the conditional return shape of llm_completion, the
bounded-gather semaphore, the PyMuPDF default, and the full removal of
litellm. No real LLM calls — we inject MockLLMClient everywhere.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
from pathlib import Path

import pytest

# NOTE: `vendor.pageindex.__init__` re-exports the `page_index` *function*, so
# `from vendor.pageindex import page_index` would bind the function, not the
# submodule. Use importlib to fetch the submodule objects unambiguously.
page_index_mod = importlib.import_module("vendor.pageindex.page_index")
pi_utils = importlib.import_module("vendor.pageindex.utils")

from llm.mock import MockLLMClient  # noqa: E402
from vendor.pageindex import set_gather_concurrency, set_llm_client  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_pageindex_state():
    """Reset the injected client and semaphore between tests so the suite is
    order-independent and we can explicitly re-test the unconfigured path."""
    pi_utils._LLM_CLIENT = None
    pi_utils._DEFAULT_MODEL = None
    page_index_mod._GATHER_SEMAPHORE = None
    yield
    pi_utils._LLM_CLIENT = None
    pi_utils._DEFAULT_MODEL = None
    page_index_mod._GATHER_SEMAPHORE = None


def test_set_llm_client_is_required():
    """llm_acompletion must raise a clear RuntimeError if the client was
    never injected."""
    with pytest.raises(RuntimeError, match="PageIndex LLM client not configured"):
        asyncio.run(pi_utils.llm_acompletion("mock-model", "hello"))


def test_mock_client_routes_through_llm_acompletion():
    """After injecting MockLLMClient, llm_acompletion should return the mock's
    echo string — proving the round-trip through backend/llm/ works."""
    set_llm_client(MockLLMClient(), default_model="mock-model")
    result = asyncio.run(pi_utils.llm_acompletion("mock-model", "say hi"))
    assert isinstance(result, str)
    assert result  # non-empty
    assert "say hi" in result  # MockLLMClient echoes the user turn


def test_llm_completion_sync_conditional_return():
    """llm_completion preserves upstream's str-or-tuple return shape."""
    set_llm_client(MockLLMClient(), default_model="mock-model")

    plain = pi_utils.llm_completion("mock-model", "hi")
    assert isinstance(plain, str)
    assert plain

    tup = pi_utils.llm_completion("mock-model", "hi", return_finish_reason=True)
    assert isinstance(tup, tuple)
    assert len(tup) == 2
    content, reason = tup
    assert isinstance(content, str)
    assert content
    assert reason == "finished"


def test_bounded_gather_respects_semaphore():
    """Set concurrency to 2 and run 6 tracked tasks; max observed parallelism
    should be <= 2."""
    set_gather_concurrency(2)

    current = 0
    peak = 0
    lock = asyncio.Lock()

    async def _task():
        nonlocal current, peak
        async with lock:
            current += 1
            if current > peak:
                peak = current
        # Small sleep to force overlap if the semaphore is broken.
        await asyncio.sleep(0.05)
        async with lock:
            current -= 1
        return "ok"

    async def _driver():
        tasks = [_task() for _ in range(6)]
        return await page_index_mod._bounded_gather(*tasks)

    results = asyncio.run(_driver())
    assert results == ["ok"] * 6
    assert peak <= 2, f"peak concurrency {peak} exceeded semaphore limit 2"


def test_pymupdf_is_default_parser():
    """get_page_tokens should default to PyMuPDF after our fork edit."""
    sig = inspect.signature(pi_utils.get_page_tokens)
    assert sig.parameters["pdf_parser"].default == "PyMuPDF"


def test_no_litellm_imports():
    """After the fork, neither vendored module should expose a `litellm`
    attribute, and no *executable* line should reference litellm. Comments
    (documenting what we ripped out) and the benign ``removeprefix("litellm/")``
    literal are allowed — we strip them before scanning."""
    # Runtime: no litellm symbol on the modules.
    assert not hasattr(pi_utils, "litellm")
    assert not hasattr(page_index_mod, "litellm")

    for src_path in (pi_utils.__file__, page_index_mod.__file__):
        src = Path(src_path).read_text()
        # Drop whole-line comments (they explain the fork; benign).
        executable = "\n".join(
            line for line in src.splitlines() if not line.lstrip().startswith("#")
        )
        # The only allowed literal mention is ``"litellm/"`` inside the legacy
        # prefix strip. Remove it before scanning.
        executable = executable.replace('"litellm/"', '""')

        assert "import litellm" not in executable, f"{src_path} still imports litellm"
        assert "litellm." not in executable, f"{src_path} still uses litellm.*"
        assert "litellm" not in executable, (
            f"{src_path} still references litellm in executable code"
        )
