"use client";

import { Fragment, type ReactNode } from "react";

// Renders the small subset of Markdown GPT uses in answers (paragraphs, bullet and
// numbered lists, **bold**, `code`) and turns [n] into clickable citation chips.

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[\d+\])/g;

function inline(text: string, onCite: (n: number) => void): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (/^`[^`]+`$/.test(part))
      return <code key={i} className="rounded bg-navy/10 px-1 py-0.5 font-mono text-[0.85em]">{part.slice(1, -1)}</code>;
    const cite = part.match(/^\[(\d+)\]$/);
    if (cite) {
      const n = Number(cite[1]);
      return (
        <button
          key={i}
          onClick={() => onCite(n)}
          className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-brand/15 px-1 align-text-top text-[11px] font-semibold text-brand-strong hover:bg-brand/30"
          title={`Source ${n}`}
        >
          {n}
        </button>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function AnswerText({ text, onCite }: { text: string; onCite: (n: number) => void }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={blocks.length} className={`my-2 space-y-1 pl-5 ${list.ordered ? "list-decimal" : "list-disc"}`}>
        {list.items.map((item, i) => <li key={i}>{inline(item, onCite)}</li>)}
      </Tag>,
    );
    list = null;
  };

  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[-*]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      if (list && list.ordered !== ordered) flush();
      list ??= { ordered, items: [] };
      list.items.push((bullet ?? numbered)![1]);
    } else {
      flush();
      if (line) blocks.push(<p key={blocks.length} className="my-2">{inline(line, onCite)}</p>);
    }
  }
  flush();

  return <div className="leading-relaxed">{blocks}</div>;
}
