"use client";

import { useState } from "react";
import { ErrorNote } from "@/components/admin/parts";
import { Icon } from "@/components/icons";
import { api, type ActionResult, type ProposedAction } from "@/lib/api";

type State = "proposed" | "running" | "done" | "failed" | "cancelled";

// How each tool reads to a person: what it does, what to call its text, and what "done" means.
const TOOLS: Record<string, { title: string; verb: string; text: string; done: string }> = {
  save_work_item: { title: "New issue", verb: "Create issue", text: "Description", done: "Issue created" },
  save_note: { title: "New comment", verb: "Post comment", text: "Comment", done: "Comment posted" },
};
const TEXT_KEYS = ["description", "body", "text"];

function StatusBadge({ state }: { state: State }) {
  const styles: Record<State, string> = {
    proposed: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    running: "bg-brand/10 text-brand-strong",
    done: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    failed: "bg-red-500/10 text-red-700 dark:text-red-400",
    cancelled: "bg-navy/10 text-muted",
  };
  const label = { proposed: "Needs your confirmation", running: "Running…", done: "Done", failed: "Failed", cancelled: "Cancelled" }[state];
  return <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${styles[state]}`}>{label}</span>;
}

// An action GitMore proposed. It shows a preview of exactly what will be written and where;
// nothing runs until the person confirms. The server checks permission again before the MCP call.
export function ActionCard({ action }: { action: ProposedAction }) {
  const tool = TOOLS[action.tool] ?? { title: action.tool, verb: "Run", text: "Text", done: "Done" };
  const [args, setArgs] = useState<Record<string, unknown>>(action.arguments);
  const [state, setState] = useState<State>(action.status === "proposed" ? "proposed" : (action.status as State));
  const [editing, setEditing] = useState(false);
  const [beforeEdit, setBeforeEdit] = useState<Record<string, unknown> | null>(null);
  const [result, setResult] = useState<ActionResult | null>(null);
  const [error, setError] = useState("");

  const textKey = TEXT_KEYS.find((k) => typeof args[k] === "string");
  const title = typeof args.title === "string" ? args.title : "";
  const text = textKey ? (args[textKey] as string) : "";
  const resultUrl = result?.result_url ?? action.result_url ?? null;

  async function confirm() {
    setState("running");
    setEditing(false);
    setError("");
    try {
      const done = await api.confirmAction(action.id, args);
      setResult(done);
      setState(done.status === "done" ? "done" : "failed");
      if (done.status !== "done") setError(done.result_text || "The tool reported a problem.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't run the action");
      setState("proposed");
    }
  }

  function startEdit() {
    setBeforeEdit(args);
    setEditing(true);
  }

  function cancelEdit() {
    if (beforeEdit) setArgs(beforeEdit); // put the text back as it was
    setEditing(false);
  }

  const field = "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15";

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-sm">
      {/* Header: what and where */}
      <div className="flex flex-wrap items-center gap-3 border-b border-border px-4 py-3">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#fc6d26] text-sm font-bold text-white" aria-hidden="true">
          {action.server.slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">{tool.title}</div>
          <div className="truncate text-xs text-muted">
            {action.server}{action.target ? <> · <span className="text-foreground">{action.target}</span></> : null}
          </div>
        </div>
        <StatusBadge state={state} />
      </div>

      {/* Preview of exactly what will be written */}
      <div className={`px-4 py-4 ${state === "cancelled" ? "opacity-60" : ""}`}>
        {editing ? (
          <div className="space-y-3">
            {typeof args.title === "string" && (
              <label className="block space-y-1">
                <span className="text-xs font-medium text-muted">Title</span>
                <input className={field} value={title} onChange={(e) => setArgs({ ...args, title: e.target.value })} />
              </label>
            )}
            {textKey && (
              <label className="block space-y-1">
                <span className="text-xs font-medium text-muted">{tool.text}</span>
                <textarea className={`${field} min-h-32 resize-y`} value={text}
                  onChange={(e) => setArgs({ ...args, [textKey]: e.target.value })} />
              </label>
            )}
          </div>
        ) : (
          <div className="rounded-lg border border-border bg-background/60 p-4">
            {title && <div className="text-[15px] font-semibold leading-snug">{title}</div>}
            {text && (
              <p className={`whitespace-pre-wrap text-sm leading-relaxed ${title ? "mt-2 text-muted" : ""}`}>{text}</p>
            )}
            {action.signature && <p className="mt-3 text-xs italic text-muted">{action.signature}</p>}
          </div>
        )}

        <ErrorNote message={error} />
      </div>

      {/* Footer: confirm, progress, or result */}
      <div className="border-t border-border bg-background/40 px-4 py-3">
        {state === "proposed" && (
          <div className="flex flex-wrap items-center gap-3">
            <p className="mr-auto text-xs text-muted">Nothing is posted until you confirm. The action is recorded.</p>
            <button onClick={editing ? cancelEdit : startEdit}
              className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
              {editing ? "Cancel edit" : "Edit"}
            </button>
            <button onClick={confirm}
              className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
              {tool.verb}
            </button>
          </div>
        )}
        {state === "running" && (
          <p className="flex items-center gap-2 text-sm text-muted">
            <span className="h-2 w-2 animate-pulse rounded-full bg-brand" /> Working in {action.server}…
          </p>
        )}
        {state === "done" && (
          <div className="space-y-3">
            <p className="flex items-center gap-2 text-sm font-medium text-emerald-700 dark:text-emerald-400">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white">
                <Icon name="check" className="h-3 w-3" strokeWidth={3} />
              </span>
              {tool.done}{action.target ? ` in ${action.target}` : ""}
            </p>
            {resultUrl && (
              <a href={resultUrl} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-4 py-2 text-sm font-medium shadow-sm hover:border-brand/60">
                Open in {action.server}
                <Icon name="chevron" className="h-4 w-4 text-muted" />
              </a>
            )}
          </div>
        )}
        {state === "failed" && <p className="text-sm text-red-700 dark:text-red-400">Nothing was confirmed as done. Check the message above.</p>}
        {state === "cancelled" && <p className="text-sm text-muted">Cancelled. Nothing was posted.</p>}
      </div>
    </div>
  );
}
