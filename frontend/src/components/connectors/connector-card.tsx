"use client";

import { useEffect, useState } from "react";
import { ErrorNote, Pill, RolesDropdown, Switch, rolesText } from "@/components/admin/parts";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { api, type Connector, type SourceAccess } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";

const KIND_LABEL = { slack: "Slack", gitlab: "GitLab" };
const CONTAINER_LABEL = { public_channel: "Public channel", private_channel: "Private channel", project: "Project" };
const INTERVALS = [5, 15, 30, 60, 180, 360, 720, 1440];

const every = (minutes: number) => (minutes < 60 ? `${minutes} min` : minutes === 1440 ? "day" : `${minutes / 60} h`);

type Ask = { title: string; detail: string; yesLabel: string; danger?: boolean; run: () => Promise<unknown> };

export function KindBadge({ kind }: { kind: Connector["kind"] }) {
  return (
    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white ${
      kind === "slack" ? "bg-[#4a154b]" : "bg-[#fc6d26]"}`} aria-hidden="true">
      {kind === "slack" ? "S" : "G"}
    </span>
  );
}

function AccessTable({ connector, roles, onChanged, ask }: {
  connector: Connector; roles: string[]; onChanged: () => void; ask: (a: Ask) => void;
}) {
  const [rows, setRows] = useState<SourceAccess[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.access(connector.id).then(setRows).catch((e) => { setError(e.message); setRows([]); });
  }, [connector.id]);

  if (rows === null) return <div className="mt-4 h-24 animate-pulse rounded-xl bg-navy/5" />;

  function pick(row: SourceAccess, role: string) {
    let next: string[];
    if (role === "all") next = row.allowed_roles.includes("all") ? [] : ["all"];
    else {
      const base = row.allowed_roles.filter((r) => r !== "all");
      next = base.includes(role) ? base.filter((r) => r !== role) : [...base, role].sort();
    }
    ask({
      title: `Change who can read ${row.container_name}?`,
      detail: `From "${rolesText(row.allowed_roles, "admins only")}" to "${rolesText(next, "admins only")}". It applies to search straight away.`,
      yesLabel: "Save access",
      danger: next.includes("all") && row.container_kind === "private_channel",
      run: async () => {
        const saved = await api.editAccess(row.id, next);
        setRows((all) => all!.map((r) => (r.id === saved.id ? saved : r)));
        onChanged();
      },
    });
  }

  return (
    <div className="mt-4 rounded-xl border border-border">
      <ErrorNote message={error} />
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
        <span>{connector.kind === "slack" ? "Channel" : "Project"}</span>
        <span>Who can read it</span>
      </div>
      <ul className="divide-y divide-border">
        {rows.map((row) => (
          <li key={row.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 font-medium">
                {row.container_kind === "private_channel" && <Icon name="lock" className="h-3.5 w-3.5 text-muted" />}
                <span className="truncate">{row.container_name}</span>
                {row.allowed_roles.length === 0 && <Pill tone="warn">Not mapped</Pill>}
              </div>
              <div className="text-xs text-muted">{CONTAINER_LABEL[row.container_kind]}</div>
            </div>
            <RolesDropdown value={row.allowed_roles} roles={["all", ...roles]} emptyLabel="Admins only" onPick={(r) => pick(row, r)} />
          </li>
        ))}
        {rows.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted">Nothing found. Check that the bot or token can see channels or projects.</li>}
      </ul>
    </div>
  );
}

export function ConnectorCard({ connector, isAdmin, roles, onChanged, onRemoved }: {
  connector: Connector;
  isAdmin: boolean;
  roles: string[];
  onChanged: (c: Connector) => void;
  onRemoved: (id: string) => void;
}) {
  const [showAccess, setShowAccess] = useState(false);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const refresh = () => api.connectors().then((all) => { const me = all.find((c) => c.id === connector.id); if (me) onChanged(me); });

  // While a sync runs, check every 2 seconds until it finishes.
  useEffect(() => {
    if (!connector.syncing) return;
    const timer = setInterval(refresh, 2000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connector.syncing]);

  async function syncNow() {
    await api.syncConnector(connector.id);
    onChanged({ ...connector, syncing: true });
  }

  const lastRun = connector.last_run;

  const statusPill = connector.syncing ? <Pill tone="brand">Syncing…</Pill>
    : !connector.enabled ? <Pill>Off</Pill>
    : connector.status === "error" ? <Pill tone="bad">Needs attention</Pill>
    : <Pill tone="good">Connected</Pill>;

  return (
    <li className={`rounded-2xl border border-border bg-surface p-5 shadow-sm ${busy ? "opacity-70" : ""}`}>
      <div className="flex flex-wrap items-start gap-4">
        <KindBadge kind={connector.kind} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-semibold">{connector.name}</h2>
            {statusPill}
            {isAdmin && connector.unmapped > 0 && <Pill tone="warn">{connector.unmapped} not mapped</Pill>}
          </div>
          <p className="mt-0.5 text-xs text-muted">
            {KIND_LABEL[connector.kind]}
            {connector.config?.team && ` · ${connector.config.team}`}
            {connector.config?.group && ` · ${connector.config.group}`}
            {" · "}
            <span title={fullDate(connector.last_sync_at)}>{connector.last_sync_at ? `synced ${timeAgo(connector.last_sync_at)}` : "not synced yet"}</span>
            {" · every "}{every(connector.sync_interval_minutes)}
            {" · "}{connector.documents} {connector.documents === 1 ? "document" : "documents"} indexed
          </p>
          <p className="mt-3 text-sm">
            <span className="text-muted">{isAdmin ? "Sources: " : "You can read: "}</span>
            {connector.you_can_read.length ? connector.you_can_read.join(", ") : <span className="text-muted">nothing yet</span>}
          </p>
        </div>
        {isAdmin && (
          <Switch on={connector.enabled} label={`${connector.name} on`} disabled={busy}
            onToggle={() => setAsk({
              title: connector.enabled ? `Turn off ${connector.name}?` : `Turn on ${connector.name}?`,
              detail: connector.enabled
                ? "It stops syncing. What's already indexed stays searchable until you remove the connector."
                : "It starts syncing again on its schedule.",
              yesLabel: connector.enabled ? "Turn off" : "Turn on",
              danger: connector.enabled,
              run: async () => onChanged(await api.editConnector(connector.id, { enabled: !connector.enabled })),
            })} />
        )}
      </div>

      {isAdmin && (
        <>
          {lastRun && !connector.syncing && (
            <p className={`mt-3 text-xs ${lastRun.status === "error" ? "text-red-700 dark:text-red-400" : "text-muted"}`}>
              Last sync ({lastRun.trigger}, {timeAgo(lastRun.finished_at ?? lastRun.started_at)}):{" "}
              {lastRun.status === "error" ? `failed: ${lastRun.error}`
                : `${lastRun.seen} found, ${lastRun.changed} new or changed, ${lastRun.deleted} removed`}
            </p>
          )}
          {connector.status === "error" && connector.last_error && (
            <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-400">{connector.last_error}</p>
          )}
          <ErrorNote message={error} />
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
            <button onClick={() => setShowAccess(!showAccess)} aria-expanded={showAccess}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">
              <Icon name="key" className="h-4 w-4 text-muted" /> Who can read what
            </button>
            <button disabled={busy || connector.syncing || !connector.enabled} onClick={() => run(syncNow)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-50">
              <Icon name="activity" className="h-4 w-4" /> {connector.syncing ? "Syncing…" : "Sync now"}
            </button>
            <button disabled={busy} onClick={() => run(async () => onChanged(await api.checkConnector(connector.id)))}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">
              <Icon name="check" className="h-4 w-4 text-muted" /> Check connection
            </button>
            <button onClick={() => setToken("")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">
              <Icon name="lock" className="h-4 w-4 text-muted" /> Replace token
              <span className="font-mono text-xs text-muted">{connector.token_hint}</span>
            </button>
            <label className="inline-flex items-center gap-2 text-sm text-muted">
              Sync every
              <select value={connector.sync_interval_minutes} disabled={busy}
                onChange={(e) => run(async () => onChanged(await api.editConnector(connector.id, { sync_interval_minutes: Number(e.target.value) })))}
                className="rounded-lg border border-border bg-surface px-2 py-1.5 text-sm text-foreground outline-none focus:border-brand">
                {INTERVALS.map((m) => <option key={m} value={m}>{every(m)}</option>)}
              </select>
            </label>
            <button onClick={() => setAsk({
                title: `Remove ${connector.name}?`,
                detail: "Its token, access mapping and everything indexed from it are deleted, so it disappears from search.",
                yesLabel: "Remove connector", danger: true,
                run: async () => { await api.removeConnector(connector.id); onRemoved(connector.id); },
              })}
              className="ml-auto rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-red-500/10 hover:text-red-600">
              Remove
            </button>
          </div>
          {showAccess && <AccessTable connector={connector} roles={roles} onChanged={refresh} ask={setAsk} />}
        </>
      )}

      {ask && (
        <ConfirmDialog title={ask.title} yesLabel={ask.yesLabel} noLabel="Cancel" tone={ask.danger ? "danger" : "brand"}
          onYes={() => { const a = ask; setAsk(null); run(a.run); }} onNo={() => setAsk(null)}>
          {ask.detail}
        </ConfirmDialog>
      )}

      {token !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => setToken(null)}>
          <form role="dialog" aria-modal="true" aria-labelledby={`token-${connector.id}`} onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => {
              e.preventDefault();
              const value = token;
              setToken(null);
              run(async () => onChanged(await api.editConnector(connector.id, { token: value })));
            }}
            className="w-full max-w-sm rounded-2xl border border-border bg-surface p-5 shadow-xl">
            <h2 id={`token-${connector.id}`} className="text-base font-semibold">Replace the {KIND_LABEL[connector.kind]} token</h2>
            <p className="mt-1 text-sm text-muted">GitMore tests it before saving. The old token is overwritten.</p>
            <input type="password" autoFocus value={token} onChange={(e) => setToken(e.target.value)} minLength={8} required
              autoComplete="off" placeholder={connector.kind === "slack" ? "xoxb-…" : "glpat-…"}
              className="mt-4 w-full rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:border-brand" />
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setToken(null)} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">Cancel</button>
              <button className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">Test and save</button>
            </div>
          </form>
        </div>
      )}
    </li>
  );
}
