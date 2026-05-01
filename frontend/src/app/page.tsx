import { redirect } from "next/navigation";

/**
 * Root path redirects to /chat — the default landing surface in the new
 * app shell (per docs/research/2026-05-02-ux-redesign-architecture.md §1).
 * The Day-1 health/LLM-test page is still reachable at /debug/llm-test
 * if you need it (move to come Day 2).
 */
export default function Home() {
  redirect("/chat");
}
