"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorNote, Pill, rolesText } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { api, type McpServer } from "@/lib/api";
import { useUser } from "@/lib/user-context";

// MCP tools let GitMore act in company tools (create an issue, post a message) after you confirm.
// Everyone sees which tools exist and which they can use; connecting servers arrives with the action route.
export default function McpPage() {
  const { user } = useUser();
  const [servers, setServers] = useState<McpServer[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) api.mcp().then(setServers).catch((e) => setError(e.message));
  }, [user]);

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="MCP tools"
        description="Actions GitMore can take for you in company tools, such as creating a GitLab issue or posting in Slack. Nothing is written until you confirm." />
      <ErrorNote message={error} />

      {servers === null && !error && <div className="h-32 animate-pulse rounded-2xl bg-navy/5" />}

      {servers?.length === 0 && (
        <EmptyState icon="tool" title="No tools connected yet">
          {user?.is_admin
            ? "Connecting the official GitLab and Slack MCP servers, turning tools on or off and choosing which roles may use them come with the action route."
            : "When your admin connects tools, you'll see them here and which ones you can use."}
        </EmptyState>
      )}

      <ul className="space-y-3">
        {servers?.map((s) => (
          <li key={s.id} className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Icon name="tool" className="h-5 w-5 text-muted" />
              <h2 className="font-semibold">{s.name}</h2>
              {s.enabled && s.status === "connected" ? <Pill tone="good">Connected</Pill> : <Pill>{s.enabled ? s.status.replace("_", " ") : "Off"}</Pill>}
            </div>
            <ul className="mt-4 divide-y divide-border rounded-xl border border-border">
              {s.tools.map((t) => (
                <li key={t.id} className="flex flex-col gap-1 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="font-medium">{t.name}</div>
                    {t.description && <div className="text-xs text-muted">{t.description}</div>}
                  </div>
                  {t.you_can_use ? <Pill tone="good">You can use it</Pill>
                    : !t.enabled ? <Pill>Off</Pill>
                    : <span className="text-xs text-muted">For {rolesText(t.allowed_roles, "admins only")}</span>}
                </li>
              ))}
              {s.tools.length === 0 && <li className="px-4 py-4 text-sm text-muted">No tools listed yet.</li>}
            </ul>
          </li>
        ))}
      </ul>
    </main>
  );
}
