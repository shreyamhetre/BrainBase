"use client";

import { useEffect, useState, type ReactNode } from "react";

// A yes/no modal. Escape or a click on the backdrop counts as "No".
// With `noteLabel`, it also asks for an optional note that is passed to onYes.
export function ConfirmDialog({ title, children, onYes, onNo, yesLabel = "Yes", noLabel = "No", tone = "brand", noteLabel }: {
  title: string;
  children?: ReactNode;
  onYes: (note: string) => void;
  onNo: () => void;
  yesLabel?: string;
  noLabel?: string;
  tone?: "brand" | "danger";
  noteLabel?: string;
}) {
  const [note, setNote] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onNo();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onNo]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 backdrop-blur-[2px]" onClick={onNo}>
      <div role="dialog" aria-modal="true" aria-labelledby="confirm-title"
        className="w-full max-w-sm rounded-2xl border border-border bg-surface p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <h2 id="confirm-title" className="text-base font-semibold">{title}</h2>
        {children && <div className="mt-2 text-sm text-muted">{children}</div>}
        {noteLabel && (
          <label className="mt-4 block space-y-1">
            <span className="text-xs font-medium text-muted">{noteLabel}</span>
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} maxLength={500}
              className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand" />
          </label>
        )}
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onNo}
            className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
            {noLabel}
          </button>
          <button onClick={() => onYes(note.trim())} autoFocus={!noteLabel}
            className={`rounded-lg px-4 py-2 text-sm font-semibold text-white ${
              tone === "danger" ? "bg-red-600 hover:bg-red-700" : "bg-brand hover:bg-brand-strong"}`}>
            {yesLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
