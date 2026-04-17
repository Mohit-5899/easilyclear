"use client";

import { Plus, Minus, ArrowsIn, ArrowClockwise } from "@phosphor-icons/react";

interface ZoomControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onReset: () => void;
}

export function ZoomControls({
  onZoomIn,
  onZoomOut,
  onFit,
  onReset,
}: ZoomControlsProps) {
  return (
    <div className="pointer-events-auto absolute bottom-6 left-1/2 z-30 -translate-x-1/2">
      <div className="flex items-center gap-1 rounded-full border border-slate-200/60 bg-white/85 p-1 shadow-[0_20px_40px_-15px_rgba(0,0,0,0.08)] backdrop-blur-xl">
        <IconButton label="Zoom out" onClick={onZoomOut}>
          <Minus size={14} weight="bold" />
        </IconButton>
        <IconButton label="Zoom in" onClick={onZoomIn}>
          <Plus size={14} weight="bold" />
        </IconButton>
        <div className="mx-1 h-5 w-px bg-slate-200" />
        <IconButton label="Fit to screen" onClick={onFit}>
          <ArrowsIn size={14} weight="bold" />
        </IconButton>
        <IconButton label="Reset" onClick={onReset}>
          <ArrowClockwise size={14} weight="bold" />
        </IconButton>
      </div>
    </div>
  );
}

function IconButton({
  children,
  label,
  onClick,
}: {
  children: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-full text-slate-600 transition-colors hover:bg-slate-100 hover:text-zinc-950 active:scale-[0.94]"
    >
      {children}
    </button>
  );
}
