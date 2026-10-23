"use client";

import { useEffect, type ReactNode } from "react";

// A yes/no modal. Escape or a click on the backdrop counts as "No".
export function ConfirmDialog({ title, children, onYes, onNo }: {
  title: string;
  children?: ReactNode;
  onYes: () => void;
  onNo: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onNo();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onNo]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={onNo}>
      <div role="dialog" aria-modal="true" aria-labelledby="confirm-title"
        className="w-full max-w-sm rounded-2xl border border-border bg-surface p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <h2 id="confirm-title" className="text-base font-semibold">{title}</h2>
        {children && <div className="mt-2 text-sm text-muted">{children}</div>}
        <div className="mt-5 flex justify-end gap-2">
          <button onClick={onNo}
            className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
            No
          </button>
          <button onClick={onYes} autoFocus
            className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
            Yes
          </button>
        </div>
      </div>
    </div>
  );
}
