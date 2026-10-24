"use client";

import { useState, type FormEvent } from "react";
import { ErrorNote, Pill } from "@/components/admin/parts";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { api, type Connector, type EventsResult } from "@/lib/api";
import { timeAgo } from "@/lib/format";

const input = "w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:border-brand";

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-muted">{label}</span>
      <span className="flex gap-2">
        <input readOnly value={value} onFocus={(e) => e.target.select()} className={input} />
        <button type="button" className="shrink-0 rounded-lg border border-border px-3 text-sm hover:border-brand/60"
          onClick={() => navigator.clipboard.writeText(value).then(() => setCopied(true), () => {})}>
          {copied ? "Copied" : "Copy"}
        </button>
      </span>
    </label>
  );
}

// Near-real-time updates for one connector: Slack Socket Mode or GitLab webhooks.
export function EventsPanel({ connector, onChanged }: { connector: Connector; onChanged: (c: Connector) => void }) {
  const [open, setOpen] = useState(false);
  const [appToken, setAppToken] = useState("");
  const [register, setRegister] = useState(true);
  const [result, setResult] = useState<EventsResult | null>(null);
  const [confirmOff, setConfirmOff] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const on = connector.events_status !== "off";
  const pill = connector.events_status === "listening" ? <Pill tone="good">On</Pill>
    : connector.events_status === "starting" ? <Pill tone="brand">Starting…</Pill>
    : connector.events_status === "error" ? <Pill tone="bad">Error</Pill>
    : <Pill>Off</Pill>;

  async function turnOn(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await api.enableEvents(connector.id, connector.kind === "slack" ? { app_token: appToken } : { register_webhooks: register });
      onChanged(res.connector);
      setAppToken("");
      if (connector.kind === "gitlab") setResult(res);
      else setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't turn on real-time updates");
    } finally {
      setBusy(false);
    }
  }

  async function turnOff() {
    setConfirmOff(false);
    try {
      onChanged(await api.disableEvents(connector.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't turn off real-time updates");
    }
  }

  return (
    <div className="mt-4 rounded-xl border border-border px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Real-time updates</span>
        {pill}
        <span className="text-xs text-muted">
          {connector.kind === "slack" ? "Slack Socket Mode" : "GitLab webhooks"}
          {connector.last_event_at && ` · last change ${timeAgo(connector.last_event_at)}`}
        </span>
        <span className="ml-auto flex gap-2">
          {on && <button onClick={() => setConfirmOff(true)} className="rounded-lg px-3 py-1 text-sm text-muted hover:bg-red-500/10 hover:text-red-600">Turn off</button>}
          <button onClick={() => { setOpen(!open); setResult(null); }} className="rounded-lg border border-border px-3 py-1 text-sm hover:border-brand/60">
            {on ? "Set up again" : "Turn on"}
          </button>
        </span>
      </div>
      {connector.events_status === "error" && connector.events_error && (
        <p className="mt-2 text-xs text-red-700 dark:text-red-400">{connector.events_error}</p>
      )}

      {open && !result && (
        <form onSubmit={turnOn} className="mt-3 space-y-3 border-t border-border pt-3 text-sm">
          {connector.kind === "slack" ? (
            <>
              <ol className="list-decimal space-y-1 pl-5 text-muted">
                <li>In your Slack app settings, turn on <b className="text-foreground">Socket Mode</b>.</li>
                <li>Under Basic Information, create an <b className="text-foreground">app-level token</b> with the <code>connections:write</code> scope.</li>
                <li>Under Event Subscriptions, subscribe to the bot events <code>message.channels</code> and <code>message.groups</code>, then reinstall the app.</li>
              </ol>
              <input type="password" autoComplete="off" required minLength={10} placeholder="xapp-…" value={appToken}
                onChange={(e) => setAppToken(e.target.value)} className={input} />
            </>
          ) : (
            <>
              <p className="text-muted">
                GitLab calls GitMore when an issue, comment or wiki page changes. It needs a public address for the API
                (set <code>PUBLIC_URL</code> in .env, for example a tunnel to port 8000).
              </p>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={register} onChange={(e) => setRegister(e.target.checked)} className="h-4 w-4 accent-[var(--brand)]" />
                Add the webhook to every project for me (the token needs the <code>api</code> scope)
              </label>
            </>
          )}
          <ErrorNote message={error} />
          <div className="flex justify-end">
            <button disabled={busy} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-60">
              {busy ? "Checking…" : connector.kind === "slack" ? "Test and turn on" : "Create webhook secret"}
            </button>
          </div>
        </form>
      )}

      {result?.secret && (
        <div className="mt-3 space-y-3 border-t border-border pt-3 text-sm">
          <p className="text-muted">Copy the secret now: it isn&apos;t shown again. Add both to each project under Settings → Webhooks if GitMore didn&apos;t add them.</p>
          <CopyField label="Webhook URL" value={connector.webhook_url ?? ""} />
          <CopyField label="Secret token" value={result.secret} />
          {result.registered.length > 0 && <p className="text-emerald-700 dark:text-emerald-400">Added to: {result.registered.join(", ")}</p>}
          {result.problems.map((p) => <p key={p} className="text-red-700 dark:text-red-400">{p}</p>)}
          <div className="flex justify-end">
            <button onClick={() => { setResult(null); setOpen(false); }} className="rounded-lg border border-border px-4 py-2 text-sm">Done</button>
          </div>
        </div>
      )}

      {confirmOff && (
        <ConfirmDialog title="Turn off real-time updates?" yesLabel="Turn off" noLabel="Cancel" tone="danger" onYes={turnOff} onNo={() => setConfirmOff(false)}>
          Changes are picked up by the scheduled sync instead, every {connector.sync_interval_minutes} minutes.
          {connector.kind === "gitlab" && " The webhooks stay in GitLab but are refused; remove them there too."}
        </ConfirmDialog>
      )}
    </div>
  );
}
