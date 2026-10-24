"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ErrorNote } from "@/components/admin/parts";
import { api, type McpServer } from "@/lib/api";

const input = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15";

const KINDS = {
  gitlab: {
    label: "GitLab", url: "https://gitlab.com/api/v4/mcp", placeholder: "glpat-…",
    help: "A fine-grained personal access token with the Duo permission “MCP tool: Execute”, plus write access to work items and notes in your group. Classic tokens don't work with GitLab's MCP server.",
  },
  slack: {
    label: "Slack", url: "https://mcp.slack.com/mcp", placeholder: "xoxp-…",
    help: "A Slack user token from your internal Slack app's OAuth login, with chat:write. Messages are sent as that user.",
  },
} as const;

type Kind = keyof typeof KINDS;

// Lists the server's tools with the token before saving. All tools start off.
export function ConnectServer({ onAdded, onClose }: { onAdded: (s: McpServer) => void; onClose: () => void }) {
  const [kind, setKind] = useState<Kind>("gitlab");
  const [name, setName] = useState("GitLab");
  const [url, setUrl] = useState<string>(KINDS.gitlab.url);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  function pick(k: Kind) {
    setKind(k);
    setName(KINDS[k].label);
    setUrl(KINDS[k].url);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onAdded(await api.addMcpServer({ kind, name, url, token }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't connect");
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => !busy && onClose()}>
      <form role="dialog" aria-modal="true" aria-labelledby="connect-mcp" onSubmit={submit} onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-xl">
        <h2 id="connect-mcp" className="text-lg font-semibold">Connect an MCP server</h2>
        <p className="mt-1 text-sm text-muted">
          GitMore lists the server&apos;s tools with this token before saving. Every tool starts off; you choose which actions to allow and for which roles.
        </p>

        <div role="radiogroup" aria-label="Server" className="mt-5 grid grid-cols-2 gap-2">
          {(Object.keys(KINDS) as Kind[]).map((k) => (
            <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => pick(k)}
              className={`rounded-xl border p-3 text-left text-sm font-medium transition ${
                kind === k ? "border-brand ring-2 ring-brand/20" : "border-border hover:border-brand/50"}`}>
              {KINDS[k].label}
              <span className="block text-xs font-normal text-muted">Official MCP server</span>
            </button>
          ))}
        </div>

        <div className="mt-5 space-y-4">
          <label className="block space-y-1">
            <span className="text-sm font-medium">Name</span>
            <input className={input} value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Server URL</span>
            <input className={`${input} font-mono`} type="url" value={url} onChange={(e) => setUrl(e.target.value)} required />
          </label>
          <label className="block space-y-1">
            <span className="text-sm font-medium">Token</span>
            <input className={`${input} font-mono`} type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)}
              required minLength={8} placeholder={KINDS[kind].placeholder} />
            <span className="block text-xs text-muted">{KINDS[kind].help} It&apos;s stored encrypted and never shown again.</span>
          </label>
        </div>

        <div className="mt-5"><ErrorNote message={error} /></div>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
            Cancel
          </button>
          <button disabled={busy} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-60">
            {busy ? "Connecting…" : "Test and connect"}
          </button>
        </div>
      </form>
    </div>
  );
}
