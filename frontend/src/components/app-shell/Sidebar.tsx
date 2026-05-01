"use client";

/**
 * Persistent left sidebar — student-facing nav (Chat, Tests, Library, Settings).
 * Admin item appears when ?admin=1 query param is present (no auth — hackathon
 * scope, see docs/research/2026-05-02-ux-redesign-architecture.md §5 Q4).
 *
 * Collapse state is sticky in localStorage. Width: 220px expanded / 56px collapsed.
 */

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ChatCircle,
  Exam,
  TreeStructure,
  Gear,
  CloudArrowUp,
  CaretLeft,
  CaretRight,
  GraduationCap,
} from "@phosphor-icons/react";

const COLLAPSE_KEY = "gemma-tutor-sidebar-collapsed";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
  match: (pathname: string) => boolean;
}

const STUDENT_NAV: NavItem[] = [
  {
    href: "/chat",
    label: "Chat",
    icon: <ChatCircle size={18} weight="duotone" />,
    match: (p) => p === "/chat" || p.startsWith("/chat/"),
  },
  {
    href: "/tests",
    label: "Tests",
    icon: <Exam size={18} weight="duotone" />,
    match: (p) => p === "/tests" || p.startsWith("/tests/") || p.startsWith("/test/"),
  },
  {
    href: "/library",
    label: "Library",
    icon: <TreeStructure size={18} weight="duotone" />,
    match: (p) => p === "/library" || p.startsWith("/library/") || p === "/explorer",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: <Gear size={18} weight="duotone" />,
    match: (p) => p === "/settings",
  },
];

const ADMIN_NAV: NavItem[] = [
  {
    href: "/admin/ingest",
    label: "Ingest",
    icon: <CloudArrowUp size={18} weight="duotone" />,
    match: (p) => p === "/admin/ingest" || p === "/ingest",
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const search = useSearchParams();
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate collapse state from localStorage.
  useEffect(() => {
    setHydrated(true);
    const saved = window.localStorage.getItem(COLLAPSE_KEY);
    if (saved === "1") setCollapsed(true);
  }, []);

  const toggle = () => {
    const next = !collapsed;
    setCollapsed(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
    }
  };

  const adminVisible =
    search?.get("admin") === "1" || pathname.startsWith("/admin");

  const widthClass = collapsed ? "w-14" : "w-56";

  return (
    <aside
      className={
        "flex h-screen flex-col border-r border-slate-200 bg-white transition-[width] duration-200 ease-out " +
        widthClass
      }
    >
      {/* Brand row */}
      <div className="flex h-14 items-center gap-2 border-b border-slate-100 px-3">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-indigo-500 text-white">
          <GraduationCap size={16} weight="bold" />
        </div>
        {!collapsed && hydrated && (
          <div className="min-w-0 leading-tight">
            <div className="truncate text-sm font-semibold tracking-tight text-zinc-950">
              Gemma Tutor
            </div>
            <div className="truncate text-[10px] text-slate-400">
              RAS Pre study assistant
            </div>
          </div>
        )}
      </div>

      {/* Primary nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        <ul className="space-y-0.5 px-2">
          {STUDENT_NAV.map((item) => (
            <NavRow
              key={item.href}
              item={item}
              active={item.match(pathname)}
              collapsed={collapsed}
            />
          ))}
        </ul>

        {adminVisible && (
          <>
            <div
              className={
                "mt-4 px-3 text-[10px] font-medium uppercase tracking-wider text-slate-400 " +
                (collapsed ? "text-center" : "")
              }
            >
              {collapsed ? "·" : "Admin"}
            </div>
            <ul className="mt-1 space-y-0.5 px-2">
              {ADMIN_NAV.map((item) => (
                <NavRow
                  key={item.href}
                  item={item}
                  active={item.match(pathname)}
                  collapsed={collapsed}
                />
              ))}
            </ul>
          </>
        )}
      </nav>

      {/* Footer: collapse toggle */}
      <div className="border-t border-slate-100 p-2">
        <button
          type="button"
          onClick={toggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex h-8 w-full items-center justify-center rounded-md text-slate-400 transition hover:bg-slate-100 hover:text-zinc-950"
        >
          {collapsed ? <CaretRight size={14} /> : <CaretLeft size={14} />}
        </button>
      </div>
    </aside>
  );
}

function NavRow({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  return (
    <li>
      <Link
        href={item.href}
        title={collapsed ? item.label : undefined}
        className={
          "flex h-9 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors " +
          (active
            ? "bg-indigo-50 text-indigo-700 font-medium"
            : "text-slate-700 hover:bg-slate-100 hover:text-zinc-950")
        }
      >
        <span className={active ? "text-indigo-600" : "text-slate-500"}>{item.icon}</span>
        {!collapsed && <span className="truncate">{item.label}</span>}
      </Link>
    </li>
  );
}
