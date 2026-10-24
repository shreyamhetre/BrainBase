"use client";

import { useState } from "react";
import { EmptyState, ErrorNote, Pill, rolesText } from "@/components/admin/parts";
import { Avatar } from "@/components/avatar";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { api, type AccessRequest } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";

const OUTCOME = {
  approved: { tone: "good", label: "Approved" },
  denied: { tone: "bad", label: "Denied" },
  cancelled: { tone: "neutral", label: "Cancelled" },
  pending: { tone: "warn", label: "Pending" },
} as const;

export function RequestsTab({ pending, decided, onDecided }: {
  pending: AccessRequest[];
  decided: AccessRequest[];
  onDecided: (request: AccessRequest) => void;
}) {
  const [asking, setAsking] = useState<{ request: AccessRequest; approve: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function decide(request: AccessRequest, approve: boolean, note: string) {
    setAsking(null);
    setBusy(request.id);
    setError("");
    try {
      onDecided(await api.decide(request.id, approve, note || null));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the decision");
    } finally {
      setBusy(null);
    }
  }

  const first = (name: string) => name.split(" ")[0];

  return (
    <div className="space-y-8">
      <section>
        <h2 className="mb-3 text-sm font-semibold">Waiting for you <span className="font-normal text-muted">({pending.length})</span></h2>
        <ErrorNote message={error} />
        {pending.length === 0 ? (
          <EmptyState icon="inbox" title="No pending requests">
            When someone asks for a role from their profile, the request shows up here for you to approve or deny.
          </EmptyState>
        ) : (
          <ul className="grid gap-3 xl:grid-cols-2">
            {pending.map((r) => (
              <li key={r.id} className={`flex flex-col rounded-2xl border border-border bg-surface p-5 shadow-sm ${busy === r.id ? "opacity-50" : ""}`}>
                <div className="flex items-start gap-3">
                  <Avatar name={r.user_name} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2">
                      <span className="font-medium">{r.user_name}</span>
                      <span className="text-xs text-muted" title={fullDate(r.created_at)}>{timeAgo(r.created_at)}</span>
                    </div>
                    <div className="truncate text-xs text-muted">{r.user_team ?? "No team"} · {r.user_email}</div>
                  </div>
                  <Pill tone="brand">wants {r.role}</Pill>
                </div>
                <blockquote className="mt-4 flex-1 rounded-lg border-l-2 border-brand/50 bg-navy/[0.03] px-4 py-3 text-sm">
                  {r.reason}
                </blockquote>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                  <span className="text-xs text-muted">Has now: {rolesText(r.user_roles)}</span>
                  <div className="flex gap-2">
                    <button disabled={!!busy} onClick={() => setAsking({ request: r, approve: false })}
                      className="rounded-lg border border-border px-3.5 py-1.5 text-sm text-muted hover:border-red-500/50 hover:text-red-600">
                      Deny
                    </button>
                    <button disabled={!!busy} onClick={() => setAsking({ request: r, approve: true })}
                      className="rounded-lg bg-brand px-3.5 py-1.5 text-sm font-semibold text-white hover:bg-brand-strong">
                      Approve
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Recent decisions</h2>
        {decided.length === 0 ? (
          <p className="text-sm text-muted">Nothing decided yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-border bg-surface shadow-sm">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <th className="px-5 py-3">Person</th>
                  <th className="px-4 py-3">Role</th>
                  <th className="px-4 py-3">Outcome</th>
                  <th className="px-4 py-3">By</th>
                  <th className="px-4 py-3">When</th>
                  <th className="px-4 py-3">Note</th>
                </tr>
              </thead>
              <tbody>
                {decided.map((r) => (
                  <tr key={r.id} className="border-b border-border last:border-0">
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2.5"><Avatar name={r.user_name} size="sm" />{r.user_name}</div>
                    </td>
                    <td className="px-4 py-3">{r.role}</td>
                    <td className="px-4 py-3"><Pill tone={OUTCOME[r.status].tone}>{OUTCOME[r.status].label}</Pill></td>
                    <td className="px-4 py-3 text-muted">{r.status === "cancelled" ? first(r.user_name) : r.decided_by ?? "—"}</td>
                    <td className="px-4 py-3 text-xs text-muted" title={fullDate(r.decided_at)}>{timeAgo(r.decided_at)}</td>
                    <td className="max-w-[16rem] truncate px-4 py-3 text-muted" title={r.note ?? ""}>{r.note || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {asking && (
        <ConfirmDialog
          title={asking.approve
            ? `Give ${asking.request.user_name} the ${asking.request.role} role?`
            : `Deny ${first(asking.request.user_name)}'s request for ${asking.request.role}?`}
          yesLabel={asking.approve ? "Approve" : "Deny"} noLabel="Cancel" tone={asking.approve ? "brand" : "danger"}
          noteLabel={`Note to ${first(asking.request.user_name)} (optional)`}
          onYes={(note) => decide(asking.request, asking.approve, note)} onNo={() => setAsking(null)}>
          {asking.approve
            ? `They can read ${asking.request.role} content from their next question.`
            : "Their roles stay the same. They see your note on their profile."}
        </ConfirmDialog>
      )}
    </div>
  );
}
