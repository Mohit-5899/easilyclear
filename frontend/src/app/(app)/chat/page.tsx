"use client";

/**
 * Agentic /chat page (Redesign D5-6, polish D8).
 *
 * Wires the AI SDK UI Message Stream protocol from /tutor/agent_chat:
 *   start-step → tool-call → tool-result → data-citation* → text-delta* →
 *   text-end → finish → [DONE]
 *
 * UI:
 *   - Recent threads rail (localStorage-backed via lib/chat-store)
 *   - Message list with inline tool-call pills
 *   - Right rail of citation cards (cross-highlight on hover)
 *   - Composer with scope picker
 *
 * Per docs/research/2026-05-02-ux-redesign-architecture.md §2.2.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  BookmarkSimple,
  ChatCircle,
  PaperPlaneRight,
  Plus,
  Spinner,
  Stop,
  Trash,
} from "@phosphor-icons/react";

import {
  deleteThread,
  deriveThreadTitle,
  getThread,
  listThreads,
  newThreadId,
  saveThread,
  type ThreadIndex,
} from "@/lib/chat-store";
import type {
  AssistantTurn,
  ChatTurn,
  Citation,
  Scope,
  ToolCallEvent,
} from "./types";

const SCOPE_OPTIONS: { value: Scope; label: string }[] = [
  { value: "all", label: "All subjects" },
  { value: "subject", label: "Current subject" },
  { value: "node", label: "Current selection" },
];

export default function ChatPage() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadIndex[]>([]);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [draft, setDraft] = useState("");
  const [scope, setScope] = useState<Scope>("all");
  const [streaming, setStreaming] = useState(false);
  const [hoveredCitation, setHoveredCitation] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Hydrate index on mount + open the most recent thread.
  useEffect(() => {
    const idx = listThreads();
    setThreads(idx);
    if (idx.length > 0) {
      const stored = getThread(idx[0].id);
      if (stored) {
        setThreadId(stored.id);
        setTurns(stored.turns);
      }
    }
  }, []);

  // Persist when turns change.
  useEffect(() => {
    if (!threadId || turns.length === 0) return;
    const firstUser = turns.find((t) => t.role === "user");
    if (!firstUser) return;
    const now = new Date().toISOString();
    const existing = getThread(threadId);
    saveThread({
      id: threadId,
      title: existing?.title ?? deriveThreadTitle(firstUser.text),
      created_at: existing?.created_at ?? now,
      updated_at: now,
      turns,
    });
    setThreads(listThreads());
  }, [turns, threadId]);

  const startNewThread = useCallback(() => {
    if (streaming) return;
    setThreadId(null);
    setTurns([]);
  }, [streaming]);

  const openThread = useCallback(
    (id: string) => {
      if (streaming) return;
      const stored = getThread(id);
      if (!stored) return;
      setThreadId(id);
      setTurns(stored.turns);
    },
    [streaming],
  );

  const removeThread = useCallback(
    (id: string, ev: React.MouseEvent) => {
      ev.stopPropagation();
      if (streaming && id === threadId) return;
      deleteThread(id);
      setThreads(listThreads());
      if (id === threadId) {
        setThreadId(null);
        setTurns([]);
      }
    },
    [streaming, threadId],
  );

  // Auto-scroll on new content
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  const allCitations = useMemo(() => {
    const out: Citation[] = [];
    for (const t of turns) {
      if (t.role === "assistant") out.push(...t.citations);
    }
    return out;
  }, [turns]);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || streaming) return;

    setDraft("");
    setStreaming(true);

    const userTurn: ChatTurn = { role: "user", text };
    const assistantSeed: AssistantTurn = {
      role: "assistant",
      text: "",
      toolCalls: [],
      citations: [],
      status: "streaming",
    };
    const newTurns = [...turns, userTurn, assistantSeed];
    setTurns(newTurns);

    if (!threadId) setThreadId(newThreadId());

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const resp = await fetch("/api/tutor/agent_chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: newTurns
            .filter((t): t is ChatTurn => t.role !== "assistant" || t.text.length > 0)
            .map((t) =>
              t.role === "user"
                ? { role: "user", content: t.text }
                : { role: "assistant", content: (t as AssistantTurn).text },
            )
            .concat([{ role: "user", content: text }]),
          default_scope: scope,
          max_steps: 3,
        }),
        signal: controller.signal,
      });

      if (!resp.ok || !resp.body) {
        throw new Error(`agent_chat failed: ${resp.status}`);
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          if (!frame.startsWith("data: ")) continue;
          const payload = frame.slice(6).trim();
          if (!payload || payload === "[DONE]") continue;
          try {
            handleEvent(JSON.parse(payload));
          } catch {
            // ignore malformed frames
          }
        }
      }

      setTurns((prev) =>
        prev.map((t, i) =>
          i === prev.length - 1 && t.role === "assistant"
            ? { ...t, status: "complete" }
            : t,
        ),
      );
    } catch (err) {
      const aborted = (err as Error).name === "AbortError";
      if (!aborted) {
        setTurns((prev) =>
          prev.map((t, i) => {
            if (i !== prev.length - 1 || t.role !== "assistant") return t;
            return {
              ...t,
              text: t.text || `[error: ${(err as Error).message}]`,
              status: "error",
            };
          }),
        );
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
    }
  }, [draft, scope, streaming, turns]);

  const handleEvent = (ev: Record<string, unknown>) => {
    const t = String(ev.type ?? "");
    if (t === "tool-call") {
      const call: ToolCallEvent = {
        id: String(ev.id ?? ""),
        query: String((ev.args as Record<string, unknown>)?.query ?? ""),
        scope:
          ((ev.args as Record<string, unknown>)?.scope as Scope) ?? "all",
        subjectSlug: ((ev.args as Record<string, unknown>)?.subject_slug
          ?? (ev.args as Record<string, unknown>)?.book_slug
          ?? undefined) as string | undefined,
        nodeId: ((ev.args as Record<string, unknown>)?.node_id ?? undefined) as
          | string
          | undefined,
      };
      appendToolCallToLastAssistant(call);
    } else if (t === "tool-result") {
      const id = String(ev.id ?? "");
      patchToolCallOnLastAssistant(id, {
        hitCount: Number(ev.hit_count ?? 0),
        scopeLabel: String(ev.scope_label ?? ""),
      });
    } else if (t === "data-citation") {
      const data = ev.data as Citation;
      appendCitationToLastAssistant(data);
    } else if (t === "text-delta") {
      const delta = String((ev as { delta?: string }).delta ?? "");
      appendDeltaToLastAssistant(delta);
    }
  };

  const appendToolCallToLastAssistant = (call: ToolCallEvent) => {
    setTurns((prev) =>
      prev.map((t, i) => {
        if (i !== prev.length - 1 || t.role !== "assistant") return t;
        return { ...t, toolCalls: [...t.toolCalls, call] };
      }),
    );
  };

  const patchToolCallOnLastAssistant = (
    id: string,
    patch: Partial<ToolCallEvent>,
  ) => {
    setTurns((prev) =>
      prev.map((t, i) => {
        if (i !== prev.length - 1 || t.role !== "assistant") return t;
        return {
          ...t,
          toolCalls: t.toolCalls.map((c) =>
            c.id === id ? { ...c, ...patch } : c,
          ),
        };
      }),
    );
  };

  const appendCitationToLastAssistant = (c: Citation) => {
    setTurns((prev) =>
      prev.map((t, i) => {
        if (i !== prev.length - 1 || t.role !== "assistant") return t;
        return { ...t, citations: [...t.citations, c] };
      }),
    );
  };

  const appendDeltaToLastAssistant = (delta: string) => {
    setTurns((prev) =>
      prev.map((t, i) => {
        if (i !== prev.length - 1 || t.role !== "assistant") return t;
        return { ...t, text: t.text + delta };
      }),
    );
  };

  const stop = () => {
    abortRef.current?.abort();
  };

  return (
    <div className="flex h-full">
      {/* Recent threads rail */}
      <aside className="hidden w-56 flex-shrink-0 border-r border-slate-200 bg-white md:flex md:flex-col">
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-3">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Threads
          </span>
          <button
            type="button"
            onClick={startNewThread}
            disabled={streaming}
            className="inline-flex items-center gap-1 rounded-md bg-zinc-950 px-2 py-1 text-[11px] font-medium text-white disabled:opacity-30"
          >
            <Plus size={10} weight="bold" /> New
          </button>
        </div>
        <ul className="flex-1 overflow-y-auto p-2">
          {threads.length === 0 ? (
            <li className="px-2 py-3 text-xs text-slate-400">
              Your conversations will appear here.
            </li>
          ) : (
            threads.map((th) => (
              <li key={th.id}>
                <button
                  type="button"
                  onClick={() => openThread(th.id)}
                  className={
                    "group flex w-full items-start justify-between gap-1 rounded-md px-2 py-1.5 text-left text-xs transition " +
                    (th.id === threadId
                      ? "bg-indigo-50 text-indigo-900"
                      : "text-slate-700 hover:bg-slate-100")
                  }
                >
                  <span className="line-clamp-2 flex-1 leading-snug">
                    {th.title}
                  </span>
                  <span
                    role="button"
                    tabIndex={0}
                    aria-label="Delete thread"
                    onClick={(ev) => removeThread(th.id, ev)}
                    onKeyDown={(ev) => {
                      if (ev.key === "Enter" || ev.key === " ") {
                        removeThread(th.id, ev as unknown as React.MouseEvent);
                      }
                    }}
                    className="invisible inline-flex h-4 w-4 cursor-pointer items-center justify-center rounded text-slate-400 hover:bg-slate-200 group-hover:visible"
                  >
                    <Trash size={10} />
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      </aside>

      {/* Main chat column */}
      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6">
          <div>
            <h1 className="text-sm font-semibold text-zinc-950">
              {threadId
                ? threads.find((th) => th.id === threadId)?.title ?? "Tutor"
                : "Tutor"}
            </h1>
            <p className="text-[11px] text-slate-500">
              Gemma searches the canonical sources and cites every claim.
            </p>
          </div>
          {turns.length > 0 && (
            <button
              type="button"
              onClick={startNewThread}
              disabled={streaming}
              className="text-xs text-slate-500 hover:text-zinc-950 disabled:opacity-30"
            >
              New thread
            </button>
          )}
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6">
          {turns.length === 0 ? (
            <EmptyState onPick={(p) => setDraft(p)} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-6">
              {turns.map((t, i) => (
                <Turn
                  key={i}
                  turn={t}
                  hoveredCitation={hoveredCitation}
                  onHoverCitation={setHoveredCitation}
                />
              ))}
              {streaming && (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <Spinner size={12} className="animate-spin" /> Thinking…
                </div>
              )}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="border-t border-slate-200 bg-white px-6 py-4">
          <div className="mx-auto max-w-3xl">
            <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm focus-within:border-indigo-400">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                rows={1}
                placeholder="Ask anything about Rajasthan geography…"
                className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-zinc-950 outline-none placeholder:text-slate-400"
                disabled={streaming}
              />
              <button
                type="button"
                onClick={streaming ? stop : send}
                disabled={!streaming && !draft.trim()}
                className="flex h-8 w-8 items-center justify-center rounded-md bg-indigo-500 text-white transition hover:bg-indigo-600 disabled:opacity-30"
                aria-label={streaming ? "Stop" : "Send"}
              >
                {streaming ? <Stop size={14} /> : <PaperPlaneRight size={14} />}
              </button>
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-slate-500">
              <label className="inline-flex items-center gap-1.5">
                Scope:
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value as Scope)}
                  className="bg-transparent text-zinc-700 focus:outline-none"
                  disabled={streaming}
                >
                  {SCOPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <span>Model: google/gemma-4-26b-a4b-it</span>
            </div>
          </div>
        </div>
      </section>

      {/* Right rail — citations */}
      <aside className="hidden w-72 flex-shrink-0 border-l border-slate-200 bg-white lg:flex lg:flex-col">
        <header className="flex h-14 items-center border-b border-slate-200 px-4">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Sources
          </h2>
        </header>
        <div className="flex-1 overflow-y-auto p-3">
          {allCitations.length === 0 ? (
            <p className="text-xs text-slate-400">
              Citations appear here as the agent retrieves source paragraphs.
            </p>
          ) : (
            <ul className="space-y-2">
              {allCitations.map((c) => (
                <li
                  key={`${c.index}-${c.node_id}-${c.paragraph_id}`}
                  onMouseEnter={() => setHoveredCitation(c.index)}
                  onMouseLeave={() => setHoveredCitation(null)}
                  className={
                    "rounded-md border bg-white p-3 text-xs transition " +
                    (hoveredCitation === c.index
                      ? "border-indigo-400 bg-indigo-50/40"
                      : "border-slate-200 hover:border-slate-300")
                  }
                >
                  <div className="flex items-center justify-between text-[10px] font-medium uppercase tracking-wider text-slate-400">
                    <span>[{c.index}] page {c.page}</span>
                    <BookmarkSimple size={10} />
                  </div>
                  <p className="mt-1.5 line-clamp-4 leading-relaxed text-slate-700">
                    {c.snippet}
                  </p>
                  <p className="mt-2 truncate font-mono text-[10px] text-slate-400">
                    {shortNodeId(c.node_id)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}

function shortNodeId(id: string): string {
  const parts = id.split("/");
  return parts.slice(-2).join("/");
}

function EmptyState({ onPick }: { onPick: (text: string) => void }) {
  const examples = [
    "Why is Aravalli called the planning region of Rajasthan?",
    "What is Mawath rainfall?",
    "Which districts have arid climate per Koppen?",
    "Name the highest peak of Aravalli with its district.",
  ];
  return (
    <div className="mx-auto flex h-full max-w-2xl items-center justify-center">
      <div className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
          <ChatCircle size={20} weight="duotone" />
        </div>
        <h2 className="mt-4 text-lg font-semibold text-zinc-950">
          Ask anything
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Gemma will search the canonical sources and cite every claim.
        </p>
        <div className="mt-6 grid gap-2 text-left">
          {examples.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => onPick(ex)}
              className="rounded-md border border-slate-200 bg-white px-4 py-2.5 text-left text-sm text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/30"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Turn({
  turn,
  hoveredCitation,
  onHoverCitation,
}: {
  turn: ChatTurn;
  hoveredCitation: number | null;
  onHoverCitation: (i: number | null) => void;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl bg-indigo-500 px-4 py-2.5 text-sm text-white">
          {turn.text}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {turn.toolCalls.map((c) => (
        <ToolCallPill key={c.id} call={c} />
      ))}
      {turn.text && (
        <div className="rounded-2xl bg-slate-100 px-4 py-3 text-sm leading-relaxed text-zinc-900">
          <RenderTextWithCitations
            text={turn.text}
            citations={turn.citations}
            hoveredCitation={hoveredCitation}
            onHoverCitation={onHoverCitation}
          />
        </div>
      )}
    </div>
  );
}

function ToolCallPill({ call }: { call: ToolCallEvent }) {
  const completed = call.hitCount !== undefined;
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-[11px] text-slate-600">
      {completed ? (
        <span className="text-emerald-500">✓</span>
      ) : (
        <Spinner size={10} className="animate-spin text-indigo-500" />
      )}
      <span className="text-slate-500">
        {completed
          ? `Found ${call.hitCount} in`
          : "Searching"}
      </span>
      <span className="font-medium text-zinc-900">
        {call.scopeLabel ?? call.query}
      </span>
    </div>
  );
}

function RenderTextWithCitations({
  text,
  citations,
  hoveredCitation,
  onHoverCitation,
}: {
  text: string;
  citations: Citation[];
  hoveredCitation: number | null;
  onHoverCitation: (i: number | null) => void;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part);
        if (!m) return <span key={i}>{part}</span>;
        const num = parseInt(m[1], 10);
        const c = citations.find((x) => x.index === num);
        const active = hoveredCitation === num;
        return (
          <span
            key={i}
            onMouseEnter={() => onHoverCitation(num)}
            onMouseLeave={() => onHoverCitation(null)}
            className={
              "mx-0.5 inline-block cursor-help rounded border px-1 text-[11px] transition " +
              (active
                ? "border-indigo-500 bg-indigo-100 text-indigo-800"
                : "border-indigo-300 bg-indigo-50 text-indigo-700")
            }
            title={c ? `${c.snippet} (page ${c.page})` : `Citation ${num}`}
          >
            [{num}]
          </span>
        );
      })}
    </>
  );
}
