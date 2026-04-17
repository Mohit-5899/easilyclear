"use client";

import {
  BookOpen,
  Buildings,
  GraduationCap,
  Funnel,
  Brain,
  Calendar,
  TreeStructure,
  CheckCircle,
} from "@phosphor-icons/react";
import type { BookData, TreeStats } from "@/lib/types";

interface BookMetadataProps {
  book: BookData;
  stats: TreeStats;
}

function ScopeBadge({ scope }: { scope: string }) {
  const isRajasthan = scope === "rajasthan";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        isRajasthan
          ? "bg-emerald-50 text-emerald-700"
          : "bg-slate-100 text-slate-600"
      }`}
    >
      {scope}
    </span>
  );
}

function MetadataRow({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span className="mt-0.5 text-slate-400">{icon}</span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">
          {label}
        </p>
        <div className="mt-0.5 text-sm text-zinc-950">{children}</div>
      </div>
    </div>
  );
}

export function BookMetadata({ book, stats }: BookMetadataProps) {
  const ingestedDate = new Date(book.ingested_at).toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="divide-y divide-slate-100 rounded-xl border border-slate-200/50 bg-white shadow-[0_20px_40px_-15px_rgba(0,0,0,0.05)]">
      <MetadataRow icon={<Buildings size={16} />} label="Publisher">
        <span className="font-medium">{book.source_publisher}</span>
        <span className="ml-2 text-xs text-slate-400">({book.source_authority})</span>
      </MetadataRow>

      <MetadataRow icon={<BookOpen size={16} />} label="Scope">
        <ScopeBadge scope={book.subject_scope} />
      </MetadataRow>

      <MetadataRow icon={<GraduationCap size={16} />} label="Exam Coverage">
        <div className="flex flex-wrap gap-1.5">
          {book.exam_coverage.map((exam) => (
            <span
              key={exam}
              className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
            >
              {exam}
            </span>
          ))}
        </div>
      </MetadataRow>

      <MetadataRow icon={<Funnel size={16} />} label="Cleaning Layers">
        <div className="flex items-center gap-1.5 flex-wrap">
          {book.cleaner_layers_applied.map((layer, i) => (
            <span key={layer} className="flex items-center gap-1">
              {i > 0 && <span className="text-slate-300 text-xs">&#8594;</span>}
              <CheckCircle size={12} weight="fill" className="text-emerald-500" />
              <span className="text-xs font-mono">{layer}</span>
            </span>
          ))}
        </div>
      </MetadataRow>

      <MetadataRow icon={<Brain size={16} />} label="LLM Model">
        <span className="font-mono text-xs">{book.llm_model_indexing}</span>
      </MetadataRow>

      <MetadataRow icon={<Calendar size={16} />} label="Ingested">
        {ingestedDate}
      </MetadataRow>

      <MetadataRow icon={<TreeStructure size={16} />} label="Stats">
        <div className="flex gap-4 font-mono text-xs">
          <span>
            <span className="text-zinc-950 font-semibold">{stats.totalNodes}</span>{" "}
            <span className="text-slate-400">nodes</span>
          </span>
          <span>
            <span className="text-zinc-950 font-semibold">{stats.maxDepth}</span>{" "}
            <span className="text-slate-400">depth</span>
          </span>
          <span>
            <span className="text-zinc-950 font-semibold">
              {stats.pageRange[0]}-{stats.pageRange[1]}
            </span>{" "}
            <span className="text-slate-400">pages</span>
          </span>
        </div>
      </MetadataRow>
    </div>
  );
}
