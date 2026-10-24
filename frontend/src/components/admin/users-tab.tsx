"use client";

import { useMemo, useState } from "react";
import { ErrorNote, RolesDropdown, Switch, rolesText } from "@/components/admin/parts";
import { Avatar } from "@/components/avatar";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { api, type AdminUser } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";

type Pending = {
  user: AdminUser;
  changes: Partial<Pick<AdminUser, "roles" | "is_active">>;
  title: string;
  detail: string;
  yesLabel: string;
  danger?: boolean;
};

const STATUSES = ["all", "active", "inactive"] as const;

export function UsersTab({ users, roles, meId, onSaved }: {
  users: AdminUser[];
  roles: string[];
  meId: string | undefined;
  onSaved: (user: AdminUser) => void;
}) {
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<(typeof STATUSES)[number]>("all");
  const [pending, setPending] = useState<Pending | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [error, setError] = useState("");

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return users.filter((u) => {
      if (statusFilter === "active" && !u.is_active) return false;
      if (statusFilter === "inactive" && u.is_active) return false;
      if (roleFilter === "none" && (u.roles.length || u.is_admin)) return false;
      if (roleFilter && roleFilter !== "none" && !u.is_admin && !u.roles.includes(roleFilter)) return false;
      return !q || [u.name, u.email, u.team ?? "", u.title ?? "", ...u.roles].join(" ").toLowerCase().includes(q);
    });
  }, [users, query, roleFilter, statusFilter]);

  async function save({ user, changes }: Pending) {
    setPending(null);
    setSaving(user.id);
    setError("");
    try {
      onSaved(await api.updateUser(user.id, changes));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the change");
    } finally {
      setSaving(null);
    }
  }

  function askRole(user: AdminUser, role: string) {
    const has = user.roles.includes(role);
    const next = has ? user.roles.filter((r) => r !== role) : [...user.roles, role].sort();
    setPending({
      user,
      changes: { roles: next },
      title: has ? `Remove the ${role} role from ${user.name}?` : `Give ${user.name} the ${role} role?`,
      detail: `Roles change from "${rolesText(user.roles)}" to "${rolesText(next)}". It applies to their next question.`,
      yesLabel: has ? "Remove role" : "Give role",
      danger: has,
    });
  }

  function askActive(user: AdminUser) {
    setPending({
      user,
      changes: { is_active: !user.is_active },
      title: user.is_active ? `Deactivate ${user.name}?` : `Reactivate ${user.name}?`,
      detail: user.is_active
        ? "They are logged out and can't log in until an admin reactivates them. Their roles are kept."
        : "They can log in again with their current roles.",
      yesLabel: user.is_active ? "Deactivate" : "Reactivate",
      danger: user.is_active,
    });
  }

  const person = (u: AdminUser) => (
    <div className="flex min-w-0 items-center gap-3">
      <Avatar name={u.name} admin={u.is_admin} />
      <div className="min-w-0">
        <div className={`truncate font-medium ${u.is_admin ? "text-brand" : ""}`}>{u.name}</div>
        <div className="truncate text-xs text-muted">{u.email}</div>
      </div>
    </div>
  );

  const team = (u: AdminUser) => (
    <div className="min-w-0">
      <div className="truncate">{u.team ?? <span className="text-muted">No team</span>}</div>
      <div className="truncate text-xs text-muted">{u.title ?? "—"}</div>
    </div>
  );

  const dropdown = (u: AdminUser) => (
    <RolesDropdown value={u.roles} roles={roles} allRoles={u.is_admin} disabled={saving === u.id} onPick={(r) => askRole(u, r)} />
  );

  const status = (u: AdminUser) => (
    <div className="flex items-center gap-2">
      <Switch on={u.is_active} label={`${u.name} active`} disabled={saving === u.id || u.id === meId} onToggle={() => askActive(u)} />
      <span className={`text-xs ${u.is_active ? "text-foreground" : "text-muted"}`}>{u.is_active ? "Active" : "Inactive"}</span>
    </div>
  );

  const lastLogin = (u: AdminUser) => (
    <span title={fullDate(u.last_login_at)} className="text-xs text-muted">{timeAgo(u.last_login_at)}</span>
  );

  const fade = (u: AdminUser) => `${saving === u.id ? "opacity-50" : ""} ${u.is_active ? "" : "bg-navy/[0.02]"}`;

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
        <label className="relative flex-1">
          <span className="sr-only">Search people</span>
          <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, email, team or title"
            className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15" />
        </label>
        <div className="flex gap-3">
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Filter by role"
            className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-brand md:flex-none">
            <option value="">All roles</option>
            {roles.map((r) => <option key={r} value={r}>{r}</option>)}
            <option value="none">Handbook only</option>
          </select>
          <div role="radiogroup" aria-label="Filter by status" className="flex rounded-lg border border-border bg-surface p-0.5">
            {STATUSES.map((s) => (
              <button key={s} role="radio" aria-checked={statusFilter === s} onClick={() => setStatusFilter(s)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium capitalize ${
                  statusFilter === s ? "bg-navy/10 text-foreground" : "text-muted hover:text-foreground"}`}>
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      <ErrorNote message={error} />

      {/* Large screens: table */}
      <div className="hidden rounded-2xl border border-border bg-surface shadow-sm lg:block">
        <table className="w-full table-fixed text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-wider text-muted">
              <th className="w-[30%] px-5 py-3">Person</th>
              <th className="w-[24%] px-4 py-3">Team</th>
              <th className="w-[22%] px-4 py-3">Roles</th>
              <th className="w-[13%] px-4 py-3">Status</th>
              <th className="w-[11%] px-4 py-3">Last login</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((u) => (
              <tr key={u.id} className={`border-b border-border transition last:border-0 hover:bg-navy/[0.03] ${fade(u)}`}>
                <td className="px-5 py-3">{person(u)}</td>
                <td className="px-4 py-3">{team(u)}</td>
                <td className="px-4 py-3">{dropdown(u)}</td>
                <td className="px-4 py-3">{status(u)}</td>
                <td className="px-4 py-3">{lastLogin(u)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 && <p className="px-5 py-10 text-center text-sm text-muted">No one matches these filters.</p>}
      </div>

      {/* Phones and tablets: cards */}
      <ul className="grid gap-3 sm:grid-cols-2 lg:hidden">
        {shown.map((u) => (
          <li key={u.id} className={`space-y-3 rounded-xl border border-border bg-surface p-4 text-sm shadow-sm ${fade(u)}`}>
            {person(u)}
            {team(u)}
            {dropdown(u)}
            <div className="flex items-center justify-between border-t border-border pt-3">
              {status(u)}
              <span className="text-xs text-muted">Last login {timeAgo(u.last_login_at)}</span>
            </div>
          </li>
        ))}
        {shown.length === 0 && <li className="py-10 text-center text-sm text-muted sm:col-span-2">No one matches these filters.</li>}
      </ul>

      <p className="mt-3 text-xs text-muted">Showing {shown.length} of {users.length} people</p>

      {pending && (
        <ConfirmDialog title={pending.title} yesLabel={pending.yesLabel} noLabel="Cancel" tone={pending.danger ? "danger" : "brand"}
          onYes={() => save(pending)} onNo={() => setPending(null)}>
          {pending.detail}
        </ConfirmDialog>
      )}
    </div>
  );
}
