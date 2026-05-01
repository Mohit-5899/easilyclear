# Streaming Chat: AI SDK 5 vs DIY SSE

## 1. Options compared

- **A. AI SDK 5**: `@ai-sdk/react` `useChat` on client; either FastAPI emits AI SDK UI Message Stream (SSE + `x-vercel-ai-ui-message-stream: v1` header), or a Next.js route proxies via `@openrouter/ai-sdk-provider` (v2.8+, out of beta).
- **B. DIY SSE**: FastAPI streams `text/event-stream` JSON chunks; client reads via `fetch` + `ReadableStream` (~50 LOC).

## 2. Tradeoffs

- OpenRouter+Gemma streaming is stable; **tool-calling has documented rough edges** (dropped `tool-input-end` events, retry loops) — risky for a hackathon.
- AI SDK 5 `data-*` parts: `writer.write({type:'data-citation', id, data})` with typed `UIMessage<never,{citation:...}>` — exactly the `text` vs `citation` shape we need, with id reconciliation.
- Model call lives in FastAPI; FastAPI emitting AI SDK wire protocol keeps one source of truth (no Next.js proxy hop).
- Bundle: `ai` + `@ai-sdk/react` ~40-60KB gz (v5 has bloat complaints) vs ~2KB DIY.
- AI SDK gives reconnect, keep-alive, `useChat` state free; DIY = manual abort + state.

## 3. DECISION

**Use AI SDK 5 on the client (`useChat`) with FastAPI emitting the AI SDK UI Message Stream protocol directly.** Keeps OpenRouter+Gemma in Python (avoids the buggy provider tool path) while getting typed `data-citation` parts and message state for free.

## 4. Implementation hints

- FastAPI: `StreamingResponse(..., media_type="text/event-stream")` + header `x-vercel-ai-ui-message-stream: v1`.
- Emit `data: {"type":"text-delta","id":"t1","delta":"..."}` and `data: {"type":"data-citation","id":"c1","data":{"paragraphId":"p_42","quote":"..."}}`, end with `data: [DONE]`.
- Frontend: `type TutorMessage = UIMessage<never, { citation: { paragraphId: string; quote: string } }>`.
- Client: `useChat<TutorMessage>({ api: '/api/tutor/chat', body: { leafId } })` (proxy through Next.js rewrite to FastAPI).
- Render via `message.parts.map`; citations as superscript chips linked to source paragraph.
- Do retrieval server-side in FastAPI before Gemma; skip AI SDK tool-calling through OpenRouter.
- Pin `ai@^5` and `@ai-sdk/react@^5`; no `@openrouter/ai-sdk-provider` needed.
- Send keep-alive comments (`: ping\n\n`) every 15s to survive proxies.
