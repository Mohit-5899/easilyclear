"use client";

export function TreeSkeleton() {
  return (
    <div className="space-y-3 p-4 animate-pulse">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3" style={{ paddingLeft: `${(i % 3) * 16}px` }}>
          <div className="h-4 w-4 rounded bg-slate-200" />
          <div className="h-4 rounded bg-slate-200" style={{ width: `${140 - (i % 3) * 20}px` }} />
          <div className="h-3 w-10 rounded bg-slate-100 ml-auto" />
        </div>
      ))}
    </div>
  );
}

export function DetailSkeleton() {
  return (
    <div className="space-y-6 p-6 animate-pulse">
      <div className="flex gap-2">
        <div className="h-4 w-16 rounded bg-slate-200" />
        <div className="h-4 w-4 rounded bg-slate-100" />
        <div className="h-4 w-24 rounded bg-slate-200" />
        <div className="h-4 w-4 rounded bg-slate-100" />
        <div className="h-4 w-20 rounded bg-slate-200" />
      </div>
      <div className="space-y-3">
        <div className="h-7 w-64 rounded bg-slate-200" />
        <div className="flex gap-3">
          <div className="h-5 w-20 rounded bg-slate-100" />
          <div className="h-5 w-16 rounded bg-slate-100" />
          <div className="h-5 w-24 rounded bg-slate-100" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="h-4 w-full rounded bg-slate-100" />
        <div className="h-4 w-5/6 rounded bg-slate-100" />
        <div className="h-4 w-4/6 rounded bg-slate-100" />
        <div className="h-4 w-5/6 rounded bg-slate-100" />
      </div>
      <div className="h-48 w-full rounded-xl bg-slate-100" />
    </div>
  );
}
