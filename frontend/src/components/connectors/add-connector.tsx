"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ErrorNote } from "@/components/admin/parts";
import { KindBadge } from "@/components/connectors/connector-card";
import { api, type Connector, type NewConnector } from "@/lib/api";

const input = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15";

const HELP = {
  slack: "A bot token (xoxb-…) from your Slack app, with channels:read, groups:read, channels:history and groups:history. Invite the bot to private channels you want indexed.",
  gitlab: "A group or personal access token (glpat-…) with read_api. GitMore only reads; actions use a separate MCP connection.",
};

// Tests the token against the tool before saving, then lists its channels or projects (all admin-only until mapped).
export function AddConnector({ onAdded, onClose }: { onAdded: (c: Connector) => void; onClose: () => void }) {
  const [kind, setKind] = useState<NewConnector["kind"]>("slack");
  const [name, setName] = useState("");
  const [token, setToken] = useState("");
  const [url, setUrl] = useState("https://gitlab.com");
  const [group, setGroup] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body: NewConnector = kind === "gitlab" ? { kind, name, token, url, group } : { kind, name, token };
      onAdded(await api.addConnector(body));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add the connector");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => !busy && onClose()}>
      <form role="dialog" aria-modal="true" aria-labelledby="add-connector" onSubmit={submit} onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-xl">
        <h2 id="add-connector" className="text-lg font-semibold">Add a connector</h2>
        <p className="mt-1 text-sm text-muted">GitMore tests the token first. New channels and projects stay admin-only until you choose who can read them.</p>

        <div role="radiogroup" aria-label="Tool" className="mt-5 grid grid-cols-2 gap-2">
          {(["slack", "gitlab"] as const).map((k) => (
            <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
              className={`flex items-center gap-3 rounded-xl border p-3 text-left text-sm font-medium transition ${
                kind === k ? "border-brand ring-2 ring-brand/20" : "border-border hover:border-brand/50"}`}>
              <KindBadge kind={k} /> {k === "slack" ? "Slack" : "GitLab"}
            </button>
          ))}
        </div>

        <div className="mt-5 space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Name</span>
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80}
              placeholder={kind === "slack" ? "Company Slack" : "Company GitLab"} />
          </label>
          {kind === "gitlab" && (
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block space-y-1">
                <span className="text-sm font-medium">GitLab URL</span>
                <input className={input} type="url" value={url} onChange={(e) => setUrl(e.target.value)} required />
              </label>
              <label className="block space-y-1">
                <span className="text-sm font-medium">Group path</span>
                <input className={input} value={group} onChange={(e) => setGroup(e.target.value)} required placeholder="my-company" />
              </label>
            </div>
          )}
          <label className="block space-y-1">
            <span className="text-sm font-medium">Token</span>
            <input className={`${input} font-mono`} type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)}
              required minLength={8} placeholder={kind === "slack" ? "xoxb-…" : "glpat-…"} />
            <span className="block text-xs text-muted">{HELP[kind]} It&apos;s stored encrypted and never shown again.</span>
          </label>
        </div>

        <div className="mt-5"><ErrorNote message={error} /></div>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
            Cancel
          </button>
          <button disabled={busy} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-60">
            {busy ? "Testing…" : "Test and add"}
          </button>
        </div>
      </form>
    </div>
  );
}
