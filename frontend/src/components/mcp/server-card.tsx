"use client";

import { useState } from "react";
import { ErrorNote, Pill, RolesDropdown, Switch, rolesText } from "@/components/admin/parts";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { api, type McpServer, type McpTool } from "@/lib/api";
import { timeAgo } from "@/lib/format";

type Ask = { title: string; detail: string; yesLabel: string; danger?: boolean; run: () => Promise<unknown> };

function ToolRow({ tool, isAdmin, roles, ask }: { tool: McpTool; isAdmin: boolean; roles: string[]; ask: (a: Ask) => void }) {
  function pickRole(role: string) {
    const current = tool.allowed_roles;
    const next = role === "all" ? (current.includes("all") ? [] : ["all"])
      : (() => { const base = current.filter((r) => r !== "all"); return base.includes(role) ? base.filter((r) => r !== role) : [...base, role].sort(); })();
    ask({
      title: `Change who can use ${tool.name}?`,
      detail: `From "${rolesText(current, "admins only")}" to "${rolesText(next, "admins only")}".`,
      yesLabel: "Save", run: () => api.editMcpTool(tool.id, { allowed_roles: next }),
    });
  }

  return (
    <li className="flex flex-col gap-2 px-4 py-3 text-sm md:flex-row md:items-center">
      <div className="min-w-0 flex-1">
        <div className="font-mono text-[13px] font-medium">{tool.name}</div>
        {tool.description && <div className="line-clamp-2 text-xs text-muted">{tool.description}</div>}
      </div>
      {isAdmin ? (
        <div className="flex items-center gap-3">
          <RolesDropdown value={tool.allowed_roles} roles={["all", ...roles]} emptyLabel="Admins only" onPick={pickRole} />
          <Switch on={tool.enabled} label={`${tool.name} on`} onToggle={() => ask({
            title: tool.enabled ? `Turn off ${tool.name}?` : `Turn on ${tool.name}?`,
            detail: tool.enabled
              ? "GitMore stops offering this action."
              : `GitMore can offer this action to ${rolesText(tool.allowed_roles, "admins only")}. Every use needs the person's confirmation and is recorded.`,
            yesLabel: tool.enabled ? "Turn off" : "Turn on", danger: tool.enabled,
            run: () => api.editMcpTool(tool.id, { enabled: !tool.enabled }),
          })} />
        </div>
      ) : tool.you_can_use ? <Pill tone="good">You can use it</Pill>
        : !tool.enabled ? <Pill>Off</Pill>
        : <span className="text-xs text-muted">For {rolesText(tool.allowed_roles, "admins only")}</span>}
    </li>
  );
}

export function ServerCard({ server, isAdmin, roles, onChanged, onRemoved }: {
  server: McpServer; isAdmin: boolean; roles: string[]; onChanged: (s: McpServer) => void; onRemoved: (id: string) => void;
}) {
  const [ask, setAsk] = useState<Ask | null>(null);
  const [showReadOnly, setShowReadOnly] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      const result = await action();
      if (result && typeof result === "object" && "tools" in result) onChanged(result as McpServer);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const actions = server.tools.filter((t) => !t.read_only);
  const readOnly = server.tools.filter((t) => t.read_only);
  const visible = isAdmin ? actions : actions.filter((t) => t.enabled);

  return (
    <li className={`rounded-2xl border border-border bg-surface p-5 shadow-sm ${busy ? "opacity-70" : ""}`}>
      <div className="flex flex-wrap items-start gap-4">
        <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white ${
          server.kind === "slack" ? "bg-[#4a154b]" : "bg-[#fc6d26]"}`} aria-hidden="true">
          {server.kind === "slack" ? "S" : "G"}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-semibold">{server.name}</h2>
            {!server.enabled ? <Pill>Off</Pill> : server.status === "error" ? <Pill tone="bad">Needs attention</Pill> : <Pill tone="good">Connected</Pill>}
          </div>
          <p className="mt-0.5 truncate text-xs text-muted">
            Official MCP server · {actions.filter((t) => t.enabled).length} of {actions.length} actions on
            {isAdmin && server.last_checked_at && ` · checked ${timeAgo(server.last_checked_at)}`}
          </p>
        </div>
        {isAdmin && (
          <Switch on={server.enabled} label={`${server.name} on`} disabled={busy} onToggle={() => setAsk({
            title: server.enabled ? `Turn off ${server.name}?` : `Turn on ${server.name}?`,
            detail: server.enabled ? "None of its actions can be used until you turn it back on." : "Its enabled actions become available again.",
            yesLabel: server.enabled ? "Turn off" : "Turn on", danger: server.enabled,
            run: () => api.editMcpServer(server.id, { enabled: !server.enabled }),
          })} />
        )}
      </div>

      {isAdmin && server.status === "error" && server.last_error && (
        <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-400">{server.last_error}</p>
      )}
      <ErrorNote message={error} />

      <div className="mt-4">
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">Actions</div>
        <ul className="divide-y divide-border rounded-xl border border-border">
          {visible.map((t) => <ToolRow key={t.id} tool={t} isAdmin={isAdmin} roles={roles} ask={setAsk} />)}
          {visible.length === 0 && <li className="px-4 py-4 text-sm text-muted">{isAdmin ? "This server offers no actions." : "No actions are turned on yet."}</li>}
        </ul>
      </div>

      {isAdmin && readOnly.length > 0 && (
        <div className="mt-3">
          <button onClick={() => setShowReadOnly(!showReadOnly)} aria-expanded={showReadOnly}
            className="inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-foreground">
            <Icon name="chevron" className={`h-3.5 w-3.5 transition ${showReadOnly ? "rotate-90" : ""}`} />
            {readOnly.length} read-only tools, not used
          </button>
          {showReadOnly && (
            <div className="mt-2 rounded-xl border border-dashed border-border px-4 py-3 text-xs text-muted">
              <p className="mb-2">These would read with this server&apos;s token, which sees more than any one person may. GitMore answers from its permission-filtered index instead, so they stay off.</p>
              <p className="font-mono">{readOnly.map((t) => t.name).join(" · ")}</p>
            </div>
          )}
        </div>
      )}

      {isAdmin && (
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <button disabled={busy} onClick={() => run(() => api.refreshMcpServer(server.id))}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">
            <Icon name="check" className="h-4 w-4 text-muted" /> Check and refresh tools
          </button>
          <button onClick={() => setToken("")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">
            <Icon name="lock" className="h-4 w-4 text-muted" /> Replace token
            <span className="font-mono text-xs text-muted">{server.token_hint}</span>
          </button>
          <button onClick={() => setAsk({
              title: `Remove ${server.name}?`, detail: "Its token and tool settings are deleted. Actions through it stop working.",
              yesLabel: "Remove server", danger: true,
              run: async () => { await api.removeMcpServer(server.id); onRemoved(server.id); },
            })}
            className="ml-auto rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-red-500/10 hover:text-red-600">
            Remove
          </button>
        </div>
      )}

      {ask && (
        <ConfirmDialog title={ask.title} yesLabel={ask.yesLabel} noLabel="Cancel" tone={ask.danger ? "danger" : "brand"}
          onYes={() => { const a = ask; setAsk(null); run(a.run); }} onNo={() => setAsk(null)}>
          {ask.detail}
        </ConfirmDialog>
      )}

      {token !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => setToken(null)}>
          <form role="dialog" aria-modal="true" aria-labelledby={`mcp-token-${server.id}`} onClick={(e) => e.stopPropagation()}
            onSubmit={(e) => { e.preventDefault(); const value = token; setToken(null); run(() => api.editMcpServer(server.id, { token: value })); }}
            className="w-full max-w-sm rounded-2xl border border-border bg-surface p-5 shadow-xl">
            <h2 id={`mcp-token-${server.id}`} className="text-base font-semibold">Replace the {server.name} token</h2>
            <p className="mt-1 text-sm text-muted">GitMore lists the tools with it before saving.</p>
            <input type="password" autoFocus value={token} onChange={(e) => setToken(e.target.value)} minLength={8} required autoComplete="off"
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
