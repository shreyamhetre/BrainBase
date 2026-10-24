"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorNote } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { ConnectServer } from "@/components/mcp/connect-server";
import { ServerCard } from "@/components/mcp/server-card";
import { api, type McpServer } from "@/lib/api";
import { useUser } from "@/lib/user-context";

// MCP tools let GitMore act in company tools (create an issue, add a comment, send a message)
// after the person confirms. Everyone sees which actions exist and which they can use; admins
// connect servers and choose which actions are on and for which roles.
export default function McpPage() {
  const { user } = useUser();
  const [servers, setServers] = useState<McpServer[] | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    api.mcp().then(setServers).catch((e) => setError(e.message));
    if (user.is_admin) api.roles().then((r) => setRoles(r.map((role) => role.name))).catch(() => {});
  }, [user]);

  const isAdmin = !!user?.is_admin;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="MCP tools"
        description="Actions GitMore can take for you in company tools, such as creating a GitLab issue. Nothing is written until you confirm, and every action is recorded."
        actions={isAdmin && (
          <button onClick={() => setAdding(true)}
            className="inline-flex items-center gap-2 self-start rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
            <Icon name="plus" className="h-4 w-4" /> Connect server
          </button>
        )} />
      <ErrorNote message={error} />

      {servers === null && !error && <div className="h-32 animate-pulse rounded-2xl bg-navy/5" />}

      {servers?.length === 0 && (
        <EmptyState icon="tool" title={isAdmin ? "Connect the GitLab MCP server" : "No tools connected yet"}>
          {isAdmin
            ? "Connect GitLab's official MCP server with a fine-grained token, then turn on the actions people may use, such as creating an issue."
            : "When your admin connects tools, you'll see them here and which ones you can use."}
        </EmptyState>
      )}

      <ul className="space-y-3">
        {servers?.map((s) => (
          <ServerCard key={s.id} server={s} isAdmin={isAdmin} roles={roles}
            onChanged={(next) => setServers((all) => all!.map((x) => (x.id === next.id ? next : x)))}
            onRemoved={(id) => setServers((all) => all!.filter((x) => x.id !== id))} />
        ))}
      </ul>

      {adding && (
        <ConnectServer onClose={() => setAdding(false)}
          onAdded={(s) => { setServers((all) => [...(all ?? []), s]); setAdding(false); }} />
      )}
    </main>
  );
}
