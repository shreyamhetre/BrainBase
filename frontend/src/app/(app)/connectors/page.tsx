"use client";

import { EmptyState, Pill } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { Icon } from "@/components/icons";
import { useUser } from "@/lib/user-context";

// Connectors copy content from company tools into GitMore's search index, with who may read it.
// Adding and managing Slack and GitLab connectors comes with the Settings work (tokens, sync, access mapping).
export default function ConnectorsPage() {
  const { user } = useUser();

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="Connectors"
        description="The sources GitMore searches when you ask a question. Each one is kept up to date automatically, and you only see what your roles allow." />

      <ul className="space-y-3">
        <li className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
          <div className="flex flex-wrap items-start gap-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 text-brand-strong">
              <Icon name="plug" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold">GitLab handbook</h2>
                <Pill tone="good">Indexed</Pill>
              </div>
              <p className="mt-1 text-sm text-muted">GitLab&apos;s public handbook: policies, benefits, engineering and security processes.</p>
              <p className="mt-2 text-xs text-muted">You can read: <span className="text-foreground">everything in it</span></p>
            </div>
          </div>
        </li>
      </ul>

      <div className="mt-6">
        <EmptyState icon="plug" title={user?.is_admin ? "Connect Slack and GitLab next" : "More sources are on the way"}>
          {user?.is_admin
            ? "Adding a connector with its token, choosing which roles can read each channel or project, and syncing are the next part of the build."
            : "When your admin connects Slack and GitLab, they appear here with the channels and projects you can read."}
        </EmptyState>
      </div>
    </main>
  );
}
