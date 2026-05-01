import { Suspense } from "react";

import { Sidebar } from "@/components/app-shell/Sidebar";

/**
 * AppShell layout — wraps every student-facing route in the persistent
 * sidebar + main content area. Routes outside this group (admin pages,
 * full-screen test mode) get the bare root layout.
 *
 * Per docs/research/2026-05-02-ux-redesign-architecture.md §1 IA.
 */
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full bg-slate-50">
      <Suspense fallback={<div className="h-screen w-14 border-r border-slate-200 bg-white" />}>
        <Sidebar />
      </Suspense>
      <main className="min-w-0 flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
