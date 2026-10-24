"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ActivityTab } from "@/components/admin/activity-tab";
import { ErrorNote } from "@/components/admin/parts";
import { RequestsTab } from "@/components/admin/requests-tab";
import { UsersTab } from "@/components/admin/users-tab";
import { PageHeader } from "@/components/app-shell";
import { Icon, type IconName } from "@/components/icons";
import { api, type AccessRequest, type Activity, type AdminUser, type Overview } from "@/lib/api";
import { useUser } from "@/lib/user-context";

const TABS = [
  { id: "users", label: "Users and roles", icon: "users" },
  { id: "requests", label: "Access requests", icon: "inbox" },
  { id: "activity", label: "Activity log", icon: "activity" },
] as const satisfies readonly { id: string; label: string; icon: IconName }[];

type Tab = (typeof TABS)[number]["id"];

function Stat({ label, value, hint, icon, highlight, onClick }: {
  label: string; value: number | string; hint: string; icon: IconName; highlight?: boolean; onClick?: () => void;
}) {
  const body = (
    <>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted">{label}</span>
        <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${highlight ? "bg-brand text-white" : "bg-navy/5 text-muted"}`}>
          <Icon name={icon} className="h-4 w-4" />
        </span>
      </div>
      <div className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className={`mt-1 text-xs ${highlight ? "font-medium text-brand-strong" : "text-muted"}`}>{hint}</div>
    </>
  );
  const box = `rounded-2xl border bg-surface p-5 text-left shadow-sm ${highlight ? "border-brand/50 ring-1 ring-brand/20" : "border-border"}`;
  return onClick
    ? <button onClick={onClick} className={`${box} transition hover:border-brand/60`}>{body}</button>
    : <div className={box}>{body}</div>;
}

function RoleBars({ counts }: { counts: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(counts));
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="text-xs font-medium text-muted">People per role</div>
      <ul className="mt-3 space-y-2">
        {Object.entries(counts).map(([role, n]) => (
          <li key={role} className="grid grid-cols-[4.5rem_1fr_1.5rem] items-center gap-2 text-xs">
            <span className="truncate text-muted">{role}</span>
            <span className="h-1.5 overflow-hidden rounded-full bg-navy/10">
              <span className="block h-full rounded-full bg-brand" style={{ width: `${(n / max) * 100}%` }} />
            </span>
            <span className="text-right tabular-nums">{n}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function NotAdmin() {
  const router = useRouter();
  return (
    <main className="flex flex-1 items-center justify-center px-4 py-16">
      <div className="max-w-sm rounded-2xl border border-border bg-surface p-8 text-center shadow-sm">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-navy/5 text-muted">
          <Icon name="lock" />
        </span>
        <h1 className="mt-4 text-lg font-semibold">Admins only</h1>
        <p className="mt-1 text-sm text-muted">
          The admin console is for GitMore admins. If you need to read more, ask for a role from your profile.
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <button onClick={() => router.back()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
            <Icon name="arrowLeft" className="h-4 w-4" /> Go back
          </button>
          <Link href="/profile#access" className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
            Request access
          </Link>
        </div>
      </div>
    </main>
  );
}

export default function AdminPage() {
  const { user: me } = useUser();
  const [tab, setTab] = useState<Tab>("users");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [pending, setPending] = useState<AccessRequest[]>([]);
  const [decided, setDecided] = useState<AccessRequest[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [error, setError] = useState("");

  // The tab lives in the URL hash (#users, #requests, #activity), so links and reloads keep it.
  useEffect(() => {
    const fromHash = () => {
      const id = window.location.hash.slice(1);
      if (TABS.some((t) => t.id === id)) setTab(id as Tab);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, []);

  const openTab = (id: Tab) => {
    setTab(id);
    history.replaceState(null, "", `#${id}`);
  };

  const refresh = useCallback(() => {
    Promise.all([api.overview(), api.requests("pending"), api.requests("decided"), api.activity()])
      .then(([o, p, d, a]) => { setOverview(o); setPending(p); setDecided(d); setActivity(a); })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!me?.is_admin) return;
    Promise.all([api.users(), api.roles()])
      .then(([u, r]) => { setUsers(u); setRoles(r); })
      .catch((e) => setError(e.message));
    refresh();
  }, [me, refresh]);

  if (me && !me.is_admin) return <NotAdmin />;

  const savedUser = (updated: AdminUser) => {
    setUsers((all) => all.map((u) => (u.id === updated.id ? updated : u)));
    refresh();
  };

  const decidedRequest = (request: AccessRequest) => {
    if (request.status === "approved") {
      setUsers((all) => all.map((u) => (u.id === request.user_id ? { ...u, roles: [...new Set([...u.roles, request.role])].sort() } : u)));
    }
    refresh();
  };

  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="Admin console" description="Manage who can use GitMore and what each person can read." />
      <ErrorNote message={error} />

      <div className="mb-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="People" icon="users" value={overview?.users ?? "–"}
          hint={overview ? `${overview.active} active · ${overview.inactive} inactive` : "Loading…"} />
        <Stat label="Active this week" icon="clock" value={overview?.active_last_7_days ?? "–"} hint="Logged in during the last 7 days" />
        <Stat label="Pending requests" icon="inbox" value={overview?.pending_requests ?? "–"}
          highlight={!!overview?.pending_requests}
          hint={overview?.pending_requests ? "Waiting for your review" : "Nothing to review"}
          onClick={() => openTab("requests")} />
        {overview ? <RoleBars counts={overview.role_counts} /> : <div className="h-36 animate-pulse rounded-2xl bg-navy/5" />}
      </div>

      <div role="tablist" aria-label="Admin sections" className="mb-6 flex gap-1 overflow-x-auto border-b border-border">
        {TABS.map((t) => {
          const count = t.id === "requests" ? pending.length : 0;
          return (
            <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => openTab(t.id)}
              className={`-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition ${
                tab === t.id ? "border-brand text-foreground" : "border-transparent text-muted hover:text-foreground"}`}>
              <Icon name={t.icon} className="h-4 w-4" />
              {t.label}
              {count > 0 && <span className="rounded-full bg-brand px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">{count}</span>}
            </button>
          );
        })}
      </div>

      <div role="tabpanel">
        {tab === "users" && <UsersTab users={users} roles={roles} meId={me?.id} onSaved={savedUser} />}
        {tab === "requests" && <RequestsTab pending={pending} decided={decided} onDecided={decidedRequest} />}
        {tab === "activity" && <ActivityTab items={activity} />}
      </div>
    </main>
  );
}
