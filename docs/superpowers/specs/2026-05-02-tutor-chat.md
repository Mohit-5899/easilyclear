# Spec — Tutor Chat (Day 19–20)

**Status**: draft · **Last updated**: 2026-05-01

## User story

A student is browsing the Springboard Rajasthan Geography skill folder in `/explorer`. She clicks the **Aravalli Mountain Range** leaf, opens the InspectorDrawer, switches to the **Chat** tab, and asks: *"Why is Aravalli called the planning region?"* Within 2-3 seconds the answer streams in, ending with a citation pill `[1]` that, when clicked, scrolls to the source paragraph in the Content tab.

## Goals

- Streaming first-token latency < 1.5s
- Every answer cites at least one source paragraph from within the selected node's subtree
- Chat state preserved per-node (switch nodes → see prior chat for THAT node)
- Works without tool-calling (Gemma 4 26B is unreliable per research)

## Non-goals

- Multi-turn cross-node conversations (chat is scoped to one node at a time)
- Image/audio inputs
- Persistent chat history across sessions (in-memory only for hackathon)

## Architecture

```
Browser (Next.js)                   FastAPI                       OpenRouter
─────────────────                   ───────                       ──────────
useChat ──► /api/tutor/chat ──┬──► retrieve(node_id, query)
            (Next.js proxy)   │     │ → BM25 over node subtree
                              │     │ → top-3 paragraphs
                              │     │
                              │     ▼
                              │   build_prompt(question, paragraphs)
                              │     │
                              │     ▼
                              └─► stream_to_ai_sdk_protocol ──► Gemma 4 26B
                                  (writes data-citation parts)    (chat completion stream)
```

Per research `2026-05-01-streaming-chat.md`: skip `@openrouter/ai-sdk-provider`, FastAPI emits the AI SDK UI Message Stream protocol directly. RAG happens server-side; Gemma never sees a "tool call" — we already gave it the relevant paragraphs.

## API contract

### `POST /api/tutor/chat`

Request body:
```json
{
  "node_id": "geography/springboard_rajasthan_geography/02-physiographic-divisions/03-characteristics-and-divisions-of-aravali",
  "messages": [{ "role": "user", "content": "Why is Aravalli called the planning region?" }],
  "book_slug": "springboard_rajasthan_geography"
}
```

Response: `text/event-stream` with header `x-vercel-ai-ui-message-stream: v1`. Stream chunks:
- `{"type":"text-delta","id":"t1","delta":"Aravalli is "}` — text tokens
- `{"type":"data-citation","id":"c1","data":{"node_id":"...","paragraph_id":42,"snippet":"...","page":18}}` — citation parts
- `{"type":"finish-step"}` — end of stream

## File layout

```
backend/
├── tutor/
│   ├── __init__.py
│   ├── retriever.py      ← BM25 over a node's subtree (50 LOC)
│   ├── prompts/
│   │   └── tutor_system.md
│   └── stream.py         ← AI SDK UI Message Stream protocol writer
├── api/
│   └── chat.py           ← POST /tutor/chat endpoint
└── tests/
    ├── test_tutor_retriever.py
    └── test_tutor_stream.py

frontend/
└── src/
    ├── app/
    │   ├── api/tutor/chat/route.ts        ← Next.js → FastAPI proxy
    │   └── explorer/components/
    │       └── InspectorDrawer/
    │           ├── ChatTab.tsx
    │           └── CitationPill.tsx
    └── lib/chat-store.ts                  ← per-node chat state (zustand or useState map)
```

## Retrieval (BM25 over subtree)

For the selected `node_id`, walk all descendant leaves, build BM25 over their `paragraph_refs` content. `query` returns top-3 `{paragraph_id, page, snippet, score}`. No embeddings needed — BM25 is enough for hackathon scale.

## Tutor prompt skeleton

```
You are a tutor helping a student prepare for the RAS Pre exam.
Answer ONLY using the provided source paragraphs. If the answer is not in
the sources, say "The provided source does not cover that". Cite each
factual claim with [1], [2], [3] mapping to source numbers below.

# Source paragraphs (selected node: {node_title})
[1] (page {page}) {paragraph_text}
[2] (page {page}) {paragraph_text}
[3] (page {page}) {paragraph_text}

# Question
{user_question}

Answer in 2-4 sentences. Be precise, exam-focused.
```

## Success criteria

5 reference questions pass (write into `tests/fixtures/reference_questions.yaml`):

1. "Why is Aravalli called the planning region?" → must cite paragraph mentioning "tribal areas, river-valley projects, mining"
2. "What is the highest peak of Aravalli?" → must cite paragraph mentioning "Gurushikhar, 1722m, Sirohi"
3. "Which districts have arid climate per Koppen?" → must cite paragraph listing "Jaisalmer, Bikaner, Churu, Sriganganagar"
4. "What is Mawath?" → must cite paragraph defining "winter rainfall from western disturbance"
5. "Name the 3 tier classification of industries by size." → must cite "Micro / Small / Medium with capital and turnover"

Each must:
- Stream first token in < 1.5s
- End with at least one valid citation
- Citation paragraph_id MUST exist in the selected node's subtree

## Edge cases

- **Empty subtree**: return error `"This node has no source content yet"`
- **Question outside source scope**: model says "not covered" instead of hallucinating
- **Stream interruption** (network drop): `useChat` retries; backend is idempotent (no state mutation)
- **Concurrent chats from same browser**: each request has its own retriever, independent

## Testing

### Backend (TDD)
- `test_tutor_retriever.py`: 4 cases — single leaf node, multi-leaf subtree, no content, query with no matches
- `test_tutor_stream.py`: 3 cases — happy stream, mid-stream error, empty paragraphs (graceful degradation)

### Frontend
- Manual smoke: 5 reference questions in browser
- Optional: Playwright e2e (deferred if time-constrained)

## Open decisions (resolved before starting)

- **Citation rendering**: pill below answer with hover preview, OR inline `[1]` markers + footnote section? → **inline markers** (matches academic norm, lighter UI)
- **Where to call BM25**: per-request rebuild OR cache per book? → **per-request** (subtree changes per node, books are small)
