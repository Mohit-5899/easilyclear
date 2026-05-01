/**
 * Chat thread persistence — localStorage-backed.
 * Per docs/research/2026-05-02-ux-redesign-architecture.md §5 Q2 (user
 * picked localStorage so refresh doesn't lose threads).
 *
 * Storage shape:
 *   gemma-tutor-threads = ThreadIndex[]   // ordered newest-first
 *   gemma-tutor-thread:<id> = StoredThread
 */

import type { ChatTurn } from "@/app/(app)/chat/types";

const INDEX_KEY = "gemma-tutor-threads";
const THREAD_PREFIX = "gemma-tutor-thread:";

export interface ThreadIndex {
  id: string;
  title: string;
  updated_at: string; // ISO
}

export interface StoredThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  turns: ChatTurn[];
}

function isClient(): boolean {
  return typeof window !== "undefined";
}

export function listThreads(): ThreadIndex[] {
  if (!isClient()) return [];
  try {
    const raw = window.localStorage.getItem(INDEX_KEY);
    if (!raw) return [];
    return JSON.parse(raw) as ThreadIndex[];
  } catch {
    return [];
  }
}

export function getThread(id: string): StoredThread | null {
  if (!isClient()) return null;
  try {
    const raw = window.localStorage.getItem(THREAD_PREFIX + id);
    return raw ? (JSON.parse(raw) as StoredThread) : null;
  } catch {
    return null;
  }
}

export function saveThread(thread: StoredThread): void {
  if (!isClient()) return;
  window.localStorage.setItem(THREAD_PREFIX + thread.id, JSON.stringify(thread));
  const index = listThreads().filter((t) => t.id !== thread.id);
  index.unshift({ id: thread.id, title: thread.title, updated_at: thread.updated_at });
  // Cap at 50 threads in the index.
  window.localStorage.setItem(INDEX_KEY, JSON.stringify(index.slice(0, 50)));
}

export function deleteThread(id: string): void {
  if (!isClient()) return;
  window.localStorage.removeItem(THREAD_PREFIX + id);
  window.localStorage.setItem(
    INDEX_KEY,
    JSON.stringify(listThreads().filter((t) => t.id !== id)),
  );
}

export function newThreadId(): string {
  return `t-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function deriveThreadTitle(firstUserMessage: string): string {
  const trimmed = firstUserMessage.trim();
  if (trimmed.length <= 60) return trimmed;
  return trimmed.slice(0, 57).trimEnd() + "…";
}
