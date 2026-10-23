"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Header } from "@/components/header";
import { api, type AdminUser } from "@/lib/api";
import { useCurrentUser } from "@/lib/use-current-user";

type Change = Partial<Pick<AdminUser, "roles" | "is_active">>;

// A change waiting for the admin to say yes or no. Nothing is saved until then.
type Pending = { user: AdminUser; changes: Change; title: string; detail: string };

function rolesText(roles: string[]) {
  return roles.length ? roles.join(", ") : "handbook only";
}

function RolesDropdown({ user, roles, disabled, onPick }: {
  user: AdminUser;
  roles: string[];
  disabled: boolean;
  onPick: (role: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // Admins hold every role; their roles aren't edited here.
  if (user.is_admin) {
    return <span className="text-sm text-muted">All roles</span>;
  }

  return (
    <div ref={box} className="relative w-full max-w-xs">
      <button type="button" disabled={disabled} onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-left text-sm hover:border-brand/60 disabled:opacity-60">
        <span className={`truncate ${user.roles.length ? "" : "text-muted"}`}>{rolesText(user.roles)}</span>
        <svg viewBox="0 0 20 20" fill="currentColor" className={`h-4 w-4 shrink-0 text-muted transition ${open ? "rotate-180" : ""}`}>
          <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.06l3.71-3.83a.75.75 0 1 1 1.08 1.04l-4.25 4.39a.75.75 0 0 1-1.08 0L5.21 8.27a.75.75 0 0 1 .02-1.06Z" clipRule="evenodd" />
        </svg>
      </button>
      {open && (
        <ul role="listbox" aria-multiselectable="true"
          className="absolute left-0 z-30 mt-1 w-full min-w-44 rounded-lg border border-border bg-surface py-1 shadow-lg">
          {roles.map((role) => {
            const on = user.roles.includes(role);
            return (
              <li key={role} role="option" aria-selected={on}>
                <button type="button" onClick={() => { setOpen(false); onPick(role); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-brand/10">
                  <span className={`flex h-4 w-4 items-center justify-center rounded border ${
                    on ? "border-brand bg-brand text-white" : "border-border"}`}>
                    {on && (
                      <svg viewBox="0 0 20 20" fill="currentColor" className="h-3 w-3">
                        <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-8 8a1 1 0 0 1-1.4 0l-4-4a1 1 0 1 1 1.4-1.4L8 12.58l7.3-7.3a1 1 0 0 1 1.4 0Z" clipRule="evenodd" />
                      </svg>
                    )}
                  </span>
                  {role}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function AdminPage() {
  const me = useCurrentUser();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  useEffect(() => {
    if (!me?.is_admin) return;
    Promise.all([api.users(), api.roles()])
      .then(([u, r]) => { setUsers(u); setRoles(r); })
      .catch((e) => setError(e.message));
  }, [me]);

  const shown = useMemo(() => {
    const f = filter.toLowerCase();
    return users.filter((u) =>
      [u.name, u.email, u.team ?? "", u.title ?? "", ...u.roles].join(" ").toLowerCase().includes(f));
  }, [users, filter]);

  async function save({ user, changes }: Pending) {
    setPending(null);
    setSaving(user.id);
    setError("");
    try {
      const updated = await api.updateUser(user.id, changes);
      setUsers((all) => all.map((u) => (u.id === updated.id ? updated : u)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
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
      detail: `Roles change from "${rolesText(user.roles)}" to "${rolesText(next)}".`,
    });
  }

  function askActive(user: AdminUser) {
    setPending({
      user,
      changes: { is_active: !user.is_active },
      title: user.is_active ? `Deactivate ${user.name}?` : `Reactivate ${user.name}?`,
      detail: user.is_active
        ? "They won't be able to log in until an admin reactivates them."
        : "They will be able to log in again with their current roles.",
    });
  }

  if (me && !me.is_admin) {
    return (
      <>
        <Header user={me} />
        <main className="mx-auto max-w-6xl px-4 py-16 text-center text-muted">Admins only.</main>
      </>
    );
  }

  const person = (user: AdminUser) => (
    <div className="min-w-0">
      <div className={`truncate font-medium ${user.is_admin ? "text-brand" : ""}`}>{user.name}</div>
      <div className="truncate text-xs text-muted">{user.email}</div>
    </div>
  );

  const team = (user: AdminUser) => (
    <div className="min-w-0">
      <div className="truncate">{user.team}</div>
      <div className="truncate text-xs text-muted">{user.title}</div>
    </div>
  );

  const active = (user: AdminUser) => (
    <input type="checkbox" aria-label={`${user.name} active`} checked={user.is_active}
      disabled={saving === user.id || user.id === me?.id}
      onChange={() => askActive(user)} className="h-4 w-4 accent-[var(--brand)] disabled:opacity-50" />
  );

  const dropdown = (user: AdminUser) => (
    <RolesDropdown user={user} roles={roles} disabled={saving === user.id} onPick={(role) => askRole(user, role)} />
  );

  const rowStyle = (user: AdminUser) =>
    `${saving === user.id ? "opacity-60" : ""} ${user.is_active ? "" : "text-muted"}`;

  return (
    <>
      <Header user={me} active="admin" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:py-8">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-xl font-semibold sm:text-2xl">Users and roles</h1>
            <p className="mt-1 text-sm text-muted">
              Everyone can read the handbook. Roles unlock restricted content.
            </p>
          </div>
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by name, team, role…"
            className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-brand sm:w-64" />
        </div>

        {error && <p className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

        {/* Large screens: table */}
        <div className="hidden rounded-2xl border border-border bg-surface lg:block">
          <table className="w-full table-fixed text-sm">
            <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="w-[26%] px-4 py-3 font-semibold">Person</th>
                <th className="w-[26%] px-4 py-3 font-semibold">Team</th>
                <th className="w-[24%] px-4 py-3 font-semibold">Roles</th>
                <th className="w-[9%] px-4 py-3 font-semibold">Active</th>
                <th className="w-[15%] px-4 py-3 font-semibold">Last login</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((user) => (
                <tr key={user.id} className={`border-b border-border last:border-0 ${rowStyle(user)}`}>
                  <td className="px-4 py-3">{person(user)}</td>
                  <td className="px-4 py-3">{team(user)}</td>
                  <td className="px-4 py-3">{dropdown(user)}</td>
                  <td className="px-4 py-3">{active(user)}</td>
                  <td className="px-4 py-3 text-xs text-muted">{user.last_login_at ?? "never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Phones and tablets: one card per person */}
        <ul className="grid gap-3 sm:grid-cols-2 lg:hidden">
          {shown.map((user) => (
            <li key={user.id} className={`rounded-xl border border-border bg-surface p-4 text-sm ${rowStyle(user)}`}>
              <div className="flex items-start justify-between gap-3">
                {person(user)}
                <label className="flex shrink-0 items-center gap-2 text-xs text-muted">
                  Active {active(user)}
                </label>
              </div>
              <div className="mt-2">{team(user)}</div>
              <div className="mt-3">{dropdown(user)}</div>
              <div className="mt-2 text-xs text-muted">Last login: {user.last_login_at ?? "never"}</div>
            </li>
          ))}
        </ul>

        <p className="mt-3 text-xs text-muted">{shown.length} of {users.length} users</p>
      </main>

      {pending && (
        <ConfirmDialog title={pending.title} onYes={() => save(pending)} onNo={() => setPending(null)}>
          {pending.detail}
        </ConfirmDialog>
      )}
    </>
  );
}
