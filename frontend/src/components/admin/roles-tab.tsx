"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ErrorNote } from "@/components/admin/parts";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { api, type AdminRole } from "@/lib/api";

const input = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15";

// Roles decide what people can read. A role can only be removed once no person or source uses it.
export function RolesTab({ onChanged }: { onChanged: () => void }) {
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<{ name: string; description: string } | null>(null);
  const [removing, setRemoving] = useState<AdminRole | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.adminRoles().then(setRoles).catch((e) => setError(e.message));
  }, []);

  async function run(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      setRoles(await api.adminRoles());
      onChanged();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      return false;
    }
  }

  async function add(e: FormEvent) {
    e.preventDefault();
    if (await run(() => api.addRole(name.trim(), description.trim()))) {
      setName("");
      setDescription("");
    }
  }

  async function saveDescription() {
    if (!editing) return;
    const { name: role, description: text } = editing;
    setEditing(null);
    await run(() => api.editRole(role, text));
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">
        Roles unlock channels, projects and tools. Give them to people in Users and roles, and to sources on the Connectors page.
      </p>
      <ErrorNote message={error} />

      <ul className="divide-y divide-border rounded-2xl border border-border bg-surface shadow-sm">
        {roles.map((r) => {
          const inUse = r.users > 0 || r.sources > 0;
          return (
            <li key={r.name} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
              <div className="min-w-0 flex-1">
                <div className="font-medium">{r.name}</div>
                {editing?.name === r.name ? (
                  <div className="mt-2 flex gap-2">
                    <input className={input} value={editing.description} maxLength={200} autoFocus
                      onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                      onKeyDown={(e) => { if (e.key === "Enter") saveDescription(); if (e.key === "Escape") setEditing(null); }} />
                    <button onClick={saveDescription} className="rounded-lg bg-brand px-3 text-sm font-semibold text-white hover:bg-brand-strong">Save</button>
                  </div>
                ) : (
                  <button onClick={() => setEditing({ name: r.name, description: r.description })}
                    className="mt-0.5 text-left text-sm text-muted hover:text-foreground">
                    {r.description || "Add a description"}
                  </button>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs text-muted">
                <span className="tabular-nums">{r.users} {r.users === 1 ? "person" : "people"}</span>
                <span className="tabular-nums">{r.sources} {r.sources === 1 ? "source" : "sources"}</span>
                <button onClick={() => setRemoving(r)} disabled={inUse}
                  title={inUse ? "Remove it from every person and source first" : `Remove ${r.name}`}
                  className="rounded-md p-1.5 hover:bg-red-500/10 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted">
                  <span className="sr-only">Remove {r.name}</span>
                  <Icon name="close" className="h-4 w-4" />
                </button>
              </div>
            </li>
          );
        })}
      </ul>

      <form onSubmit={add} className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <h3 className="text-sm font-semibold">Add a role</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-[12rem_1fr_auto]">
          <label>
            <span className="sr-only">Role name</span>
            <input className={input} value={name} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="e.g. finance"
              pattern="[a-z][a-z0-9\-]{1,30}" title="Lowercase letters, numbers and dashes" required />
          </label>
          <label>
            <span className="sr-only">Description</span>
            <input className={input} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={200}
              placeholder="What it unlocks, e.g. Budgets and finance channels" />
          </label>
          <button className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-50"
            disabled={name.trim().length < 2}>Add role</button>
        </div>
      </form>

      {removing && (
        <ConfirmDialog title={`Remove the ${removing.name} role?`} yesLabel="Remove role" noLabel="Cancel" tone="danger"
          onYes={() => { const r = removing; setRemoving(null); run(() => api.deleteRole(r.name)); }}
          onNo={() => setRemoving(null)}>
          Nobody holds it and no source uses it. Open requests for it are cancelled.
        </ConfirmDialog>
      )}
    </div>
  );
}
