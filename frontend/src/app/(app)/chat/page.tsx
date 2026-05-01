"use client";

/**
 * Placeholder /chat page — the real agentic chat lands Days 5-6 per
 * docs/research/2026-05-02-ux-redesign-architecture.md §4. This stub
 * lets the AppShell + Sidebar ship Day 1 with a working default route.
 */

import Link from "next/link";
import { ArrowRight, ChatCircle, Sparkle } from "@phosphor-icons/react";

export default function ChatPage() {
  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center border-b border-slate-200 bg-white px-6">
        <h1 className="text-sm font-semibold text-zinc-950">Chat</h1>
      </header>

      <div className="flex flex-1 items-center justify-center px-6">
        <div className="max-w-md text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <ChatCircle size={22} weight="duotone" />
          </div>
          <h2 className="mt-5 text-lg font-semibold text-zinc-950">
            Agentic chat is coming
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">
            Type a question — Gemma will look up the right paragraphs across
            every ingested book and answer with citations. Wiring lands
            Days 5–6 of the redesign sprint.
          </p>

          <div className="mt-6 grid gap-2 text-left">
            <Link
              href="/library"
              className="group flex items-center justify-between rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/50"
            >
              <span className="inline-flex items-center gap-2">
                <Sparkle size={14} className="text-indigo-500" />
                Browse the Library
              </span>
              <ArrowRight
                size={14}
                className="text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-indigo-500"
              />
            </Link>
            <Link
              href="/tests"
              className="group flex items-center justify-between rounded-md border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/50"
            >
              <span className="inline-flex items-center gap-2">
                <Sparkle size={14} className="text-indigo-500" />
                Generate a mock test
              </span>
              <ArrowRight
                size={14}
                className="text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-indigo-500"
              />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
