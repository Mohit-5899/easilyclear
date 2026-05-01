"use client";

/**
 * Settings — model toggle, default scope, language. Stub for Day 1; full
 * implementation isn't on the critical path.
 */

import { useEffect, useState } from "react";

const SCOPE_KEY = "gemma-tutor-default-scope";
const LANG_KEY = "gemma-tutor-language";

export default function SettingsPage() {
  const [scope, setScope] = useState<"all" | "book" | "node">("all");
  const [language, setLanguage] = useState<"english" | "hindi">("english");

  useEffect(() => {
    const s = window.localStorage.getItem(SCOPE_KEY);
    if (s === "all" || s === "book" || s === "node") setScope(s);
    const l = window.localStorage.getItem(LANG_KEY);
    if (l === "english" || l === "hindi") setLanguage(l);
  }, []);

  const update = <T extends string>(key: string, value: T, set: (v: T) => void) => {
    set(value);
    if (typeof window !== "undefined") window.localStorage.setItem(key, value);
  };

  return (
    <div className="flex h-full flex-col">
      <header className="flex h-14 items-center border-b border-slate-200 bg-white px-6">
        <h1 className="text-sm font-semibold text-zinc-950">Settings</h1>
      </header>
      <div className="space-y-8 px-6 py-8">
        <Field label="Default chat scope" hint="What does Gemma search across when you start a new thread?">
          <select
            value={scope}
            onChange={(e) =>
              update(SCOPE_KEY, e.target.value as "all" | "book" | "node", setScope)
            }
            className="w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <option value="all">All books</option>
            <option value="book">Current book only</option>
            <option value="node">Current selection only</option>
          </select>
        </Field>

        <Field label="Answer language" hint="Gemma will respond in this language.">
          <select
            value={language}
            onChange={(e) =>
              update(
                LANG_KEY,
                e.target.value as "english" | "hindi",
                setLanguage,
              )
            }
            className="w-64 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
          >
            <option value="english">English</option>
            <option value="hindi">हिन्दी (Hindi)</option>
          </select>
        </Field>

        <Field label="Model" hint="Which model handles the heavy lifting.">
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-mono text-slate-600">
            google/gemma-4-26b-a4b-it
          </span>
        </Field>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-zinc-950">{label}</h2>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
      <div className="mt-3">{children}</div>
    </div>
  );
}
