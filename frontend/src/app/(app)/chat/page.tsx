"use client";

/**
 * Agentic /chat page (Redesign D5-6, polish D8).
 *
 * Pure orchestration: thread persistence, layout shell, callbacks. Streaming
 * lives in `./hooks/useAgentStream`; UI panels are split into
 * `./components/*`. Per docs/research/2026-05-02-ux-redesign-architecture.md §2.2.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Spinner } from "@phosphor-icons/react";

import {
  deleteThread,
  deriveThreadTitle,
  getThread,
  listThreads,
  newThreadId,
  saveThread,
  type ThreadIndex,
} from "@/lib/chat-store";
import type { Citation, Scope } from "./types";
import { ChatComposer } from "./components/ChatComposer";
import { CitationsRail } from "./components/CitationsRail";
import { EmptyState } from "./components/EmptyState";
import { ThreadsRail } from "./components/ThreadsRail";
import { Turn } from "./components/Turn";
import { useAgentStream } from "./hooks/useAgentStream";

export default function ChatPage() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threads, setThreads] = useState<ThreadIndex[]>([]);
  const [draft, setDraft] = useState("");
  const [scope, setScope] = useState<Scope>("all");
  const [hoveredCitation, setHoveredCitation] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { turns, streaming, send, stop, reset } = useAgentStream();

  useEffect(() => {
    const idx = listThreads();
    setThreads(idx);
    if (idx.length > 0) {
      const stored = getThread(idx[0].id);
      if (stored) {
        setThreadId(stored.id);
        reset(stored.turns);
      }
    }
  }, [reset]);

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

  const startNewThread = useCallback(() => {
    if (streaming) return;
    setThreadId(null);
    reset([]);
  }, [streaming, reset]);

  const openThread = useCallback(
    (id: string) => {
      if (streaming) return;
      const stored = getThread(id);
      if (!stored) return;
      setThreadId(id);
      reset(stored.turns);
    },
    [streaming, reset],
  );

  const removeThread = useCallback(
    (id: string, ev: React.MouseEvent) => {
      ev.stopPropagation();
      if (streaming && id === threadId) return;
      deleteThread(id);
      setThreads(listThreads());
      if (id === threadId) {
        setThreadId(null);
        reset([]);
      }
    },
    [streaming, threadId, reset],
  );

  const handleSend = useCallback(() => {
    const text = draft.trim();
    if (!text || streaming) return;
    setDraft("");
    if (!threadId) setThreadId(newThreadId());
    void send(text, scope);
  }, [draft, scope, streaming, threadId, send]);

  const headerTitle = threadId
    ? threads.find((th) => th.id === threadId)?.title ?? "Tutor"
    : "Tutor";

  return (
    <div className="flex h-full">
      <ThreadsRail
        threads={threads}
        activeId={threadId}
        streaming={streaming}
        onNewThread={startNewThread}
        onOpen={openThread}
        onDelete={removeThread}
      />

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6">
          <div>
            <h1 className="text-sm font-semibold text-zinc-950">
              {headerTitle}
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

        <ChatComposer
          draft={draft}
          onDraftChange={setDraft}
          scope={scope}
          onScopeChange={setScope}
          streaming={streaming}
          onSend={handleSend}
          onStop={stop}
        />
      </section>

      <CitationsRail
        citations={allCitations}
        hoveredCitation={hoveredCitation}
        onHover={setHoveredCitation}
      />
    </div>
  );
}
