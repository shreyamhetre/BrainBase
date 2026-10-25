"use client";

import { useState } from "react";
import { ActionCard } from "@/components/action-card";
import { Icon } from "@/components/icons";
import type { ProposedAction } from "@/lib/api";

// What "do it for me" fills into the message box for each tool.
const START_COMMAND: Record<string, { label: string; text: string }> = {
  save_work_item: { label: "Create an issue for me", text: "Create an issue in " },
  save_note: { label: "Add a comment for me", text: "Add a comment on issue " },
};

// Under a how-to answer: one click starts the command in the message box, ready to finish and send.
export function OfferAction({ tool, onStart }: { tool: string; onStart: (text: string) => void }) {
  const offer = START_COMMAND[tool];
  if (!offer) return null;
  return (
    <button onClick={() => onStart(offer.text)}
      className="mt-4 inline-flex items-center gap-2 rounded-lg border border-brand/40 bg-brand/5 px-3 py-1.5 text-sm font-medium text-brand-strong hover:bg-brand/10">
      <Icon name="tool" className="h-4 w-4" /> {offer.label}
    </button>
  );
}

// The message could mean "how do I…" or "do it": the person picks. Both readings were prepared by
// the router, so "Explain" asks the prepared question and "Create" shows the drafted action card.
export function ChooseReply({ text, question, action, onExplain }: {
  text: string; question: string; action: ProposedAction | null; onExplain: (question: string) => void;
}) {
  const [picked, setPicked] = useState<"explain" | "do" | null>(
    action && action.status !== "proposed" ? "do" : null);
  const doLabel = action?.tool === "save_note" ? "Add the comment" : "Create the issue";

  return (
    <div>
      <p className="text-sm leading-relaxed">{text}</p>
      {picked === null && (
        <div className="mt-4 flex flex-wrap gap-2">
          <button onClick={() => { setPicked("explain"); onExplain(question); }}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium hover:border-brand/60">
            Explain the process
          </button>
          {action && (
            <button onClick={() => setPicked("do")}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
              {doLabel}
            </button>
          )}
        </div>
      )}
      {picked === "explain" && <p className="mt-3 text-xs text-muted">Explaining below.</p>}
      {picked === "do" && action && <div className="mt-4"><ActionCard action={action} /></div>}
    </div>
  );
}
