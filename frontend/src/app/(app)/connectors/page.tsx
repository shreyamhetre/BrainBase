"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorNote, Pill } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { AddConnector } from "@/components/connectors/add-connector";
import { ConnectorCard } from "@/components/connectors/connector-card";
import { Icon } from "@/components/icons";
import { api, type Connector } from "@/lib/api";
import { useUser } from "@/lib/user-context";

// Connectors copy content from company tools into GitMore's search index, with who may read it.
// Everyone sees what is connected and what they can read; admins manage them here.
export default function ConnectorsPage() {
  const { user } = useUser();
  const [connectors, setConnectors] = useState<Connector[] | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    api.connectors().then(setConnectors).catch((e) => setError(e.message));
    if (user.is_admin) api.roles().then((r) => setRoles(r.map((role) => role.name))).catch(() => {});
  }, [user]);

  const isAdmin = !!user?.is_admin;
  const replace = (c: Connector) => setConnectors((all) => all!.map((x) => (x.id === c.id ? c : x)));

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="Connectors"
        description={isAdmin
          ? "Tools GitMore indexes, and who can read each channel or project. New ones are admin-only until you map them."
          : "The sources GitMore searches when you ask a question. You only see what your roles allow."}
        actions={isAdmin && (
          <button onClick={() => setAdding(true)}
            className="inline-flex items-center gap-2 self-start rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
            <Icon name="plus" className="h-4 w-4" /> Add connector
          </button>
        )} />
      <ErrorNote message={error} />

      <ul className="space-y-3">
        <li className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="flex items-start gap-4">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-navy text-surface">
              <Icon name="chat" className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold">GitLab handbook</h2>
                <Pill tone="good">Indexed</Pill>
              </div>
              <p className="mt-0.5 text-xs text-muted">Built in · public handbook pages</p>
              <p className="mt-3 text-sm"><span className="text-muted">You can read: </span>everything in it</p>
            </div>
          </div>
        </li>

        {connectors === null && !error && <li className="h-32 animate-pulse rounded-2xl bg-navy/5" />}
        {connectors?.map((c) => (
          <ConnectorCard key={c.id} connector={c} isAdmin={isAdmin} roles={roles} onChanged={replace}
            onRemoved={(id) => setConnectors((all) => all!.filter((x) => x.id !== id))} />
        ))}
      </ul>

      {connectors?.length === 0 && (
        <div className="mt-6">
          <EmptyState icon="plug" title={isAdmin ? "Connect Slack or GitLab" : "More sources are on the way"}>
            {isAdmin
              ? "Add a connector with its token. GitMore lists its channels or projects so you can choose who reads each one."
              : "When your admin connects Slack or GitLab, they appear here with the channels and projects you can read."}
          </EmptyState>
        </div>
      )}

      {adding && (
        <AddConnector onClose={() => setAdding(false)}
          onAdded={(c) => { setConnectors((all) => [...(all ?? []), c]); setAdding(false); }} />
      )}
    </main>
  );
}
