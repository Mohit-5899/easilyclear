"use client";

/**
 * ChatTab — tutor chat scoped to the currently-selected skill node.
 *
 * Per spec 2026-05-02-tutor-chat.md. Talks to /api/tutor/chat, reads the
 * AI SDK UI Message Stream wire format, renders streamed text + citation
 * pills. We parse the stream directly (no useChat) because AI SDK 6's
 * useChat shape is API-evolving and the wire protocol is small.
 */

import { useCallback, useRef, useState } from "react";
import { PaperPlaneRight, BookmarkSimple, Stop } from "@phosphor-icons/react";

interface ChatTabProps {
  nodeId: string;
  nodeName: string;
  bookSlug: string;
}

interface Citation {
  index: number;
  node_id: string;
  paragraph_id: number;
  page: number;
  snippet: string;
}

interface ChatTurn {
  role: "user" | "assistant";
  text: string;
  citations: Citation[];
}

export function ChatTab({ nodeId, nodeName, bookSlug }: ChatTabProps) {
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async () => {
    const question = draft.trim();
    if (!question || isStreaming) return;

    const userTurn: ChatTurn = { role: "user", text: question, citations: [] };
    setHistory((h) => [...h, userTurn, { role: "assistant", text: "", citations: [] }]);
    setDraft("");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch("/api/tutor/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          node_id: nodeId,
          messages: [{ role: "user", content: question }],
          book_slug: bookSlug,
        }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        throw new Error(`tutor chat failed: ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Each SSE frame is "data: <json>\n\n".
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!frame.startsWith("data: ")) continue;
          const payload = frame.slice(6).trim();
          if (!payload || payload === "[DONE]") continue;

          let event: { type: string; [k: string]: unknown };
          try {
            event = JSON.parse(payload);
          } catch {
            continue;
          }

          if (event.type === "data-citation") {
            const data = event.data as Citation;
            setHistory((h) => {
              const next = [...h];
              const last = next[next.length - 1];
              if (last && last.role === "assistant") {
                last.citations = [...last.citations, data];
              }
              return next;
            });
          } else if (event.type === "text-delta") {
            const delta = (event as { delta?: string }).delta ?? "";
            setHistory((h) => {
              const next = [...h];
              const last = next[next.length - 1];
              if (last && last.role === "assistant") {
                last.text = last.text + delta;
              }
              return next;
            });
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setHistory((h) => {
          const next = [...h];
          const last = next[next.length - 1];
          if (last && last.role === "assistant" && !last.text) {
            last.text = `[error: ${(err as Error).message}]`;
          }
          return next;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [draft, isStreaming, nodeId, bookSlug]);

  const stop = () => {
    abortRef.current?.abort();
  };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-slate-100 px-4 py-3 text-xs text-slate-500">
        Chatting about <span className="font-medium text-zinc-950">{nodeName}</span>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {history.length === 0 ? (
          <p className="text-sm text-slate-500">
            Ask a question about this topic. Answers will cite the source paragraphs.
          </p>
        ) : (
          history.map((turn, i) => (
            <div key={i} className={turn.role === "user" ? "text-right" : ""}>
              <div
                className={
                  "inline-block max-w-[90%] rounded-lg px-3 py-2 text-sm " +
                  (turn.role === "user"
                    ? "bg-indigo-500 text-white"
                    : "bg-slate-100 text-zinc-900")
                }
              >
                <RenderTextWithCitations
                  text={turn.text || (turn.role === "assistant" && isStreaming ? "…" : "")}
                  citations={turn.citations}
                />
              </div>
              {turn.role === "assistant" && turn.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {turn.citations.map((c) => (
                    <span
                      key={c.index}
                      className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600"
                      title={c.snippet}
                    >
                      <BookmarkSimple size={10} />
                      [{c.index}] page {c.page}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <div className="border-t border-slate-100 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask a question…"
            className="flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-zinc-950 placeholder:text-slate-400 outline-none focus:border-indigo-400"
            disabled={isStreaming}
          />
          <button
            type="button"
            onClick={isStreaming ? stop : sendMessage}
            disabled={!isStreaming && !draft.trim()}
            className="rounded-md bg-indigo-500 px-3 text-white transition hover:bg-indigo-600 disabled:opacity-30"
            aria-label={isStreaming ? "Stop" : "Send"}
          >
            {isStreaming ? <Stop size={16} /> : <PaperPlaneRight size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}

function RenderTextWithCitations({
  text,
  citations,
}: {
  text: string;
  citations: Citation[];
}) {
  // Replace [N] tokens with styled spans.
  if (!text) return null;
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const num = parseInt(m[1], 10);
        const c = citations.find((x) => x.index === num);
        return (
          <span
            key={i}
            className="mx-0.5 inline-block rounded border border-indigo-300 bg-indigo-50 px-1 text-[11px] text-indigo-700"
            title={c ? `${c.snippet} (page ${c.page})` : `Citation ${num}`}
          >
            [{num}]
          </span>
        );
      })}
    </>
  );
}
