"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { EmptyState, Pill } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { Avatar } from "@/components/avatar";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { api, type MyRequest, type Role, type User } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";
import { useUser } from "@/lib/user-context";

const input = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15 disabled:opacity-60";
const primary = "rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-50";

function Section({ id, title, description, children }: { id?: string; title: string; description: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 grid gap-4 border-t border-border py-8 md:grid-cols-[16rem_1fr] md:gap-8">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      <div className="min-w-0 rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">{children}</div>
    </section>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
    </label>
  );
}

function Status({ ok, error }: { ok: string; error: string }) {
  if (error) return <p role="alert" className="text-sm text-red-600 dark:text-red-400">{error}</p>;
  if (ok) return <p role="status" className="text-sm text-emerald-700 dark:text-emerald-400">{ok}</p>;
  return null;
}

const REQUEST_TONE = { pending: "warn", approved: "good", denied: "bad", cancelled: "neutral" } as const;

export default function ProfilePage() {
  const { user, setUser } = useUser();
  if (!user) return <main className="flex-1" />;
  return <Profile user={user} setUser={setUser} />;
}

function Profile({ user, setUser }: { user: User; setUser: (user: User) => void }) {
  const [name, setName] = useState(user.name);
  const [title, setTitle] = useState(user.title ?? "");
  const [team, setTeam] = useState(user.team ?? "");
  const [profileMsg, setProfileMsg] = useState({ ok: "", error: "" });

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [passwordMsg, setPasswordMsg] = useState({ ok: "", error: "" });

  const [requests, setRequests] = useState<MyRequest[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [role, setRole] = useState("");
  const [reason, setReason] = useState("");
  const [requestMsg, setRequestMsg] = useState({ ok: "", error: "" });
  const [cancelling, setCancelling] = useState<MyRequest | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user.is_admin) return;
    api.myRequests().then(setRequests).catch(() => {});
    api.roles().then(setRoles).catch(() => {});
  }, [user.is_admin]);

  useEffect(() => {
    if (window.location.hash === "#access") document.getElementById("access")?.scrollIntoView();
  }, []);

  const pendingRoles = new Set(requests.filter((r) => r.status === "pending").map((r) => r.role));
  const requestable = roles.filter((r) => !user.roles.includes(r.name) && !pendingRoles.has(r.name));

  async function saveProfile(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setProfileMsg({ ok: "", error: "" });
    try {
      setUser(await api.updateProfile({ name, title: title || null, team: team || null }));
      setProfileMsg({ ok: "Profile saved.", error: "" });
    } catch (err) {
      setProfileMsg({ ok: "", error: err instanceof Error ? err.message : "Couldn't save your profile" });
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(e: FormEvent) {
    e.preventDefault();
    if (next !== confirm) return setPasswordMsg({ ok: "", error: "The new passwords don't match." });
    setBusy(true);
    setPasswordMsg({ ok: "", error: "" });
    try {
      await api.changePassword(current, next);
      setCurrent(""); setNext(""); setConfirm("");
      setPasswordMsg({ ok: "Password changed. Use it next time you log in.", error: "" });
    } catch (err) {
      setPasswordMsg({ ok: "", error: err instanceof Error ? err.message : "Couldn't change your password" });
    } finally {
      setBusy(false);
    }
  }

  async function sendRequest(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setRequestMsg({ ok: "", error: "" });
    try {
      const created = await api.requestRole(role, reason);
      setRequests((all) => [created, ...all]);
      setRole(""); setReason("");
      setRequestMsg({ ok: `Request sent. You'll see the admin's answer here.`, error: "" });
    } catch (err) {
      setRequestMsg({ ok: "", error: err instanceof Error ? err.message : "Couldn't send the request" });
    } finally {
      setBusy(false);
    }
  }

  async function cancel(request: MyRequest) {
    setCancelling(null);
    try {
      await api.cancelRequest(request.id);
      setRequests((all) => all.map((r) => (r.id === request.id ? { ...r, status: "cancelled" } : r)));
    } catch (err) {
      setRequestMsg({ ok: "", error: err instanceof Error ? err.message : "Couldn't cancel the request" });
    }
  }

  const profileChanged = name.trim() !== user.name || (title || null) !== user.title || (team || null) !== user.team;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="Profile" description="Your details, password and access." />

      <div className="mb-2 flex items-center gap-4 rounded-2xl border border-border bg-surface p-5 shadow-sm">
        <Avatar name={user.name} admin={user.is_admin} size="lg" />
        <div className="min-w-0">
          <div className={`truncate text-lg font-semibold ${user.is_admin ? "text-brand" : ""}`}>{user.name}</div>
          <div className="truncate text-sm text-muted">{user.email}</div>
          <div className="mt-2 flex flex-wrap gap-1">
            {user.is_admin ? <Pill tone="brand">Admin · all roles</Pill>
              : user.roles.length ? user.roles.map((r) => <Pill key={r} tone="brand">{r}</Pill>)
              : <Pill>Handbook only</Pill>}
          </div>
        </div>
      </div>

      <Section title="Details" description="How you appear to others in GitMore.">
        <form onSubmit={saveProfile} className="space-y-4">
          <Field label="Name"><input className={input} value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Title"><input className={input} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={100} /></Field>
            <Field label="Team"><input className={input} value={team} onChange={(e) => setTeam(e.target.value)} maxLength={100} /></Field>
          </div>
          <Field label="Email" hint="Your email is your login, so only an admin can change it.">
            <input className={input} value={user.email} disabled />
          </Field>
          <div className="flex items-center justify-between gap-3">
            <Status {...profileMsg} />
            <button className={`${primary} ml-auto`} disabled={busy || !profileChanged || !name.trim()}>Save changes</button>
          </div>
        </form>
      </Section>

      <Section title="Password" description="At least 8 characters. You stay logged in on this device.">
        <form onSubmit={savePassword} className="space-y-4">
          <Field label="Current password">
            <input className={input} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="New password">
              <input className={input} type="password" autoComplete="new-password" minLength={8} value={next} onChange={(e) => setNext(e.target.value)} required />
            </Field>
            <Field label="Repeat new password">
              <input className={input} type="password" autoComplete="new-password" minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
            </Field>
          </div>
          <div className="flex items-center justify-between gap-3">
            <Status {...passwordMsg} />
            <button className={`${primary} ml-auto`} disabled={busy}>Change password</button>
          </div>
        </form>
      </Section>

      <Section id="access" title="Access" description="Roles decide which channels, projects and documents GitMore searches for you.">
        {user.is_admin ? (
          <p className="text-sm text-muted">As an admin you hold every role, so GitMore searches everything.</p>
        ) : (
          <div className="space-y-6">
            <form onSubmit={sendRequest} className="space-y-4">
              <h3 className="text-sm font-semibold">Request a role</h3>
              {requestable.length === 0 ? (
                <p className="text-sm text-muted">You already have or have asked for every role.</p>
              ) : (
                <>
                  <Field label="Role">
                    <select className={input} value={role} onChange={(e) => setRole(e.target.value)} required>
                      <option value="" disabled>Choose a role</option>
                      {requestable.map((r) => <option key={r.name} value={r.name}>{r.name}{r.description ? ` · ${r.description}` : ""}</option>)}
                    </select>
                  </Field>
                  <Field label="Why do you need it?" hint="The admin sees this when deciding.">
                    <textarea className={`${input} resize-none`} rows={3} minLength={5} maxLength={500} value={reason}
                      onChange={(e) => setReason(e.target.value)} required
                      placeholder="For example: I'm covering hiring for the People team this quarter." />
                  </Field>
                  <div className="flex items-center justify-between gap-3">
                    <Status {...requestMsg} />
                    <button className={`${primary} ml-auto`} disabled={busy || !role || reason.trim().length < 5}>Send request</button>
                  </div>
                </>
              )}
            </form>

            <div>
              <h3 className="mb-3 text-sm font-semibold">Your requests</h3>
              {requests.length === 0 ? (
                <EmptyState icon="inbox" title="No requests yet">Requests you send appear here with the admin&apos;s answer.</EmptyState>
              ) : (
                <ul className="divide-y divide-border rounded-xl border border-border">
                  {requests.map((r) => (
                    <li key={r.id} className="flex flex-col gap-2 p-4 text-sm sm:flex-row sm:items-start">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium">{r.role}</span>
                          <Pill tone={REQUEST_TONE[r.status]}>{r.status}</Pill>
                          <span className="text-xs text-muted" title={fullDate(r.created_at)}>asked {timeAgo(r.created_at)}</span>
                        </div>
                        <p className="mt-1 text-muted">{r.reason}</p>
                        {r.note && <p className="mt-1 text-xs"><span className="text-muted">Admin:</span> {r.note}</p>}
                      </div>
                      {r.status === "pending" && (
                        <button onClick={() => setCancelling(r)} className="self-start text-xs font-medium text-muted hover:text-red-600">
                          Cancel request
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </Section>

      {cancelling && (
        <ConfirmDialog title={`Cancel your request for ${cancelling.role}?`} yesLabel="Cancel request" noLabel="Keep it" tone="danger"
          onYes={() => cancel(cancelling)} onNo={() => setCancelling(null)}>
          The admin won&apos;t see it any more. You can ask again later.
        </ConfirmDialog>
      )}
    </main>
  );
}
