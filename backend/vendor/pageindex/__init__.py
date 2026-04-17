"""Vendored PageIndex — MIT-licensed, forked from github.com/VectifyAI/PageIndex.

Upstream commit: f2dcffc0 (``git rev-parse HEAD`` at vendoring time).

See ARCHITECTURE.md §11 for why we vendor instead of pip-installing, and for
the list of local edits. In short:

1. ``utils.py`` — rewrote ``llm_completion`` / ``llm_acompletion`` to route
   through ``backend/llm/`` (``set_llm_client`` is the single injection point);
   dropped ``litellm`` and replaced ``litellm.token_counter`` with a 4-chars/
   token heuristic; flipped ``get_page_tokens`` default parser to PyMuPDF;
   made PyPDF2 a lazy import so it's no longer a hard dependency.
2. ``page_index.py`` — wrapped all 5 ``asyncio.gather(...)`` sites with a
   shared-semaphore ``_bounded_gather`` helper so concurrent LLM calls stay
   under OpenRouter rate limits. ``set_gather_concurrency(n)`` tunes the cap.
3. ``retrieve.py`` — tool functions vendored verbatim aside from making the
   PyPDF2 import lazy (the gemma-tutor path always uses cached pages).

The three public surfaces from this package:

* :func:`page_index` — the top-level indexer. Pass a PDF path or BytesIO; use
  :func:`set_gather_concurrency` beforehand to pick a concurrency limit.
* :func:`set_llm_client` — inject a :class:`backend.llm.base.LLMClient` once
  at startup. PageIndex fans out into it for every LLM call.
* :func:`set_gather_concurrency` — set the shared semaphore limit (default 5).
"""

from .page_index import page_index, set_gather_concurrency
from .utils import set_llm_client

__all__ = ["page_index", "set_llm_client", "set_gather_concurrency"]
