"use client";

import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownContentProps {
  body: string;
}

const components: Components = {
  h1: ({ children }) => (
    <h1 className="mt-4 mb-2 text-base font-semibold text-zinc-950">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-4 mb-1.5 text-sm font-semibold text-zinc-950">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3 mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
      {children}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-3 mb-1 text-xs font-semibold text-zinc-950">
      {children}
    </h4>
  ),
  p: ({ children }) => (
    <p className="mb-2 text-sm leading-relaxed text-slate-700">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 list-disc space-y-0.5 pl-5 text-sm leading-relaxed text-slate-700">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 list-decimal space-y-0.5 pl-5 text-sm leading-relaxed text-slate-700">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-zinc-950">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-emerald-700 underline underline-offset-2 hover:text-emerald-800"
    >
      {children}
    </a>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <code className={`font-mono text-xs ${className ?? ""}`}>
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-xs text-zinc-900">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg border border-slate-100 bg-slate-50 p-3 font-mono text-xs">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-slate-200 pl-3 text-sm italic text-slate-600">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-slate-100" />,
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="min-w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-slate-200 px-2 py-1 text-left font-semibold text-zinc-950">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-slate-100 px-2 py-1 text-slate-700">
      {children}
    </td>
  ),
};

export function MarkdownContent({ body }: MarkdownContentProps) {
  const trimmed = body.trim();
  if (!trimmed) return null;

  return (
    <div className="mt-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {trimmed}
      </ReactMarkdown>
    </div>
  );
}
