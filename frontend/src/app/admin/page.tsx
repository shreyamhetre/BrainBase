"use client";

import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/header";
import { api, type AdminUser } from "@/lib/api";
import { useCurrentUser } from "@/lib/use-current-user";

export default function AdminPage() {
  const me = useCurrentUser();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<string | null>(null);

  useEffect(() => {
    if (!me?.is_admin) return;
    Promise.all([api.users(), api.roles()])
      .then(([u, r]) => { setUsers(u); setRoles(r); })
      .catch((e) => setError(e.message));
  }, [me]);

  const shown = useMemo(() => {
    const f = filter.toLowerCase();
    return users.filter((u) => [u.name, u.email, u.team ?? "", ...u.roles].join(" ").toLowerCase().includes(f));
  }, [users, filter]);

  async function update(user: AdminUser, changes: Partial<Pick<AdminUser, "roles" | "is_admin" | "is_active">>) {
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

  function toggleRole(user: AdminUser, role: string) {
    const next = user.roles.includes(role) ? user.roles.filter((r) => r !== role) : [...user.roles, role];
    update(user, { roles: next });
  }

  if (me && !me.is_admin) {
    return (
      <>
        <Header user={me} active="admin" />
        <main className="mx-auto max-w-6xl px-4 py-16 text-center text-muted">Admins only.</main>
      </>
    );
  }

  return (
    <>
      <Header user={me} active="admin" />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Users and roles</h1>
            <p className="mt-1 text-sm text-muted">
              Everyone can read the handbook. Roles unlock restricted content: click a role to give or remove it.
            </p>
          </div>
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter by name, team, role…"
            className="w-64 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-brand" />
        </div>

        {error && <p className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

        <div className="overflow-x-auto rounded-2xl border border-border bg-surface">
          <table className="w-full text-sm">
            <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Person</th>
                <th className="px-4 py-3 font-semibold">Team</th>
                <th className="px-4 py-3 font-semibold">Roles</th>
                <th className="px-4 py-3 font-semibold">Admin</th>
                <th className="px-4 py-3 font-semibold">Active</th>
                <th className="px-4 py-3 font-semibold">Last login</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((user) => (
                <tr key={user.id} className={`border-b border-border last:border-0 ${saving === user.id ? "opacity-60" : ""} ${user.is_active ? "" : "text-muted"}`}>
                  <td className="px-4 py-3">
                    <div className="font-medium">{user.name}</div>
                    <div className="text-xs text-muted">{user.email}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div>{user.team}</div>
                    <div className="text-xs text-muted">{user.title}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {roles.map((role) => {
                        const on = user.roles.includes(role);
                        return (
                          <button key={role} onClick={() => toggleRole(user, role)} disabled={saving === user.id}
                            className={`rounded-full px-2 py-0.5 text-xs font-medium transition ${
                              on ? "bg-brand text-white" : "border border-border text-muted hover:border-brand/60"}`}>
                            {role}
                          </button>
                        );
                      })}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={user.is_admin} disabled={saving === user.id || user.id === me?.id}
                      onChange={() => update(user, { is_admin: !user.is_admin })} className="h-4 w-4 accent-[var(--brand)]" />
                  </td>
                  <td className="px-4 py-3">
                    <input type="checkbox" checked={user.is_active} disabled={saving === user.id || user.id === me?.id}
                      onChange={() => update(user, { is_active: !user.is_active })} className="h-4 w-4 accent-[var(--brand)]" />
                  </td>
                  <td className="px-4 py-3 text-xs text-muted">{user.last_login_at ?? "never"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">{shown.length} of {users.length} users</p>
      </main>
    </>
  );
}
