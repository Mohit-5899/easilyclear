# Gemma Tutor — Architecture Diagram

> Visual reference for the Kaggle submission. Render the Mermaid blocks below in any tool that supports Mermaid (GitHub README preview, mermaid.live, Obsidian, Notion, etc.) to export PNG/SVG for the writeup.

## High-level system

```mermaid
flowchart TB
    subgraph "Browser — Next.js 16 (port 3001)"
        EX["/explorer<br/>radial knowledge map"]
        TST["/test/[id]<br/>full-screen MCQ"]
        ING["/ingest<br/>upload PDF"]
    end

    subgraph "FastAPI backend (port 8010)"
        CHAT["POST /tutor/chat<br/>BM25 + AI SDK stream"]
        TESTS["POST /tests<br/>3-stage MCQ generator"]
        INGEST["POST /ingest<br/>SSE pipeline runner"]
        LLM["LLMClient Protocol"]
    end

    subgraph "Models"
        OR["Gemma 4 26B<br/>via OpenRouter"]
        OLLAMA["Gemma 4 e4b/e2b<br/>via Ollama (offline)"]
        MOCK["Mock LLM<br/>(unit tests)"]
    end

    subgraph "Storage (JSON files)"
        SKILLS["database/skills/<br/>YAML frontmatter +<br/>verbatim Markdown"]
    end

    EX -->|"useChat SSE"| CHAT
    EX -->|"createMockTest"| TESTS
    TST -->|"grade"| TESTS
    ING -->|"multipart"| INGEST

    CHAT --> LLM
    TESTS --> LLM
    INGEST --> LLM

    LLM --> OR
    LLM --> OLLAMA
    LLM --> MOCK

    CHAT -.read.-> SKILLS
    TESTS -.read.-> SKILLS
    INGEST -.write.-> SKILLS
```

## V2 ingestion pipeline (8 stages)

```mermaid
flowchart LR
    PDF[Source PDF] --> S1
    subgraph S1 ["1. Extract"]
        PYMU[PyMuPDF text]
        OCR["1.5 Tesseract OCR<br/>(map labels, tables)"]
        PYMU --> MERGE[merge + branding cleanup]
        OCR --> MERGE
    end
    S1 --> S2
    subgraph S2 ["2. Pre-structure"]
        BOOK[bookmarks → draft chapters]
    end
    S2 --> S4
    subgraph S4 ["4. Decompose<br/>Gemma multi-agent"]
        PROP[Proposer]
        CRIT[Critic]
        REF[Refinement]
        PROP --> CRIT --> REF
    end
    S4 -->|"Pydantic structural validator<br/>retries up to 5x"| S5
    subgraph S5 ["5. Validate"]
        COV["95% coverage gate<br/>+ no nulls / overlaps"]
    end
    S5 --> S6
    subgraph S6 ["6. Title refine"]
        TR["Gemma rewrites titles<br/>from actual content"]
    end
    S6 --> S65
    subgraph S65 ["6.5 Dedup<br/>(cross-book)"]
        EMB[BGE cosine prefilter]
        JUDGE[Gemma grey-zone judge]
        EMB --> JUDGE
    end
    S65 --> S7
    subgraph S7 ["7. Content fill"]
        DET["deterministic<br/>verbatim concat<br/>NO LLM"]
    end
    S7 --> S8
    subgraph S8 ["8. Emit"]
        FOLDER["skill folder:<br/>YAML + Markdown"]
    end
```

## Mock test generator (3 stages)

```mermaid
flowchart LR
    INPUT[selected node + paragraphs] --> GEN
    subgraph GEN ["1. Generator"]
        G1["Gemma 4 26B<br/>JSON-mode<br/>oversample to 13"]
    end
    GEN --> VER
    subgraph VER ["2. Verifier (deterministic)"]
        V1["answer_span must be<br/>substring of cited paragraph"]
    end
    VER --> JUDGE
    subgraph JUDGE ["3. LLM Judge"]
        J1["single_correct?<br/>grounded?<br/>leakage?"]
    end
    JUDGE --> OUT[trim to 10 questions]
    OUT --> SERVE[POST /tests response]
```

## Tutor chat data flow

```mermaid
sequenceDiagram
    actor Student
    participant Frontend as Frontend (ChatTab)
    participant Proxy as Next.js /api/tutor/chat
    participant API as FastAPI /tutor/chat
    participant BM25 as BM25 Retriever
    participant LLM as Gemma 4 26B

    Student->>Frontend: types question
    Frontend->>Proxy: POST {node_id, message}
    Proxy->>API: forwards (same body)
    API->>BM25: search subtree, k=3
    BM25-->>API: top-3 paragraphs
    API->>API: build_tutor_messages<br/>(numbered sources)
    API->>LLM: stream() chat completion
    loop tokens
        LLM-->>API: delta
        API-->>Proxy: SSE: text-delta
        Proxy-->>Frontend: SSE: text-delta
        Frontend-->>Student: render
    end
    API-->>Frontend: SSE: data-citation x N
    Frontend-->>Student: citation pills
```

## Why these specific choices

| Decision | Reason | Spec |
|---|---|---|
| Source preservation (no LLM paraphrasing) | Trustworthy citations + ground truth for MCQ verification | A.1 |
| Pydantic structural validator | Catches null leaves & overlapping ranges at parse time, retries with feedback to Gemma | A.9 |
| Tesseract OCR (Stage 1.5) | 100% of audit pages had image-rendered content invisible to PyMuPDF | A.10 |
| Title refiner (Stage 6) | Gemma drifts one section header late; refining from content fixes it without touching ranges | A.11 |
| BM25 over subtree (not full book) | Bounded retrieval; chat is scoped to selected node anyway | tutor-chat |
| AI SDK UI Message Stream protocol direct from FastAPI | Skip the buggy `@openrouter/ai-sdk-provider` (per research note) | streaming-chat |
| 3-stage MCQ pipeline | MMLU-Pro recipe; deterministic verifier replaces expert review (free) | mcq-generation |
| BGE-small + Gemma judge dedup | Local embeddings cheap; LLM only for grey-zone pairs | dedup |

Spec details: see `docs/superpowers/specs/2026-04-17-v2-ingestion-pipeline-design.md` and the per-feature specs from 2026-05-02 onward.
