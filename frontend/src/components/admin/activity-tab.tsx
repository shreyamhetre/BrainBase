"use client";

import { useMemo, useState, type ReactNode } from "react";
import { EmptyState } from "@/components/admin/parts";
import { Avatar } from "@/components/avatar";
import type { Activity } from "@/lib/api";
import { dayLabel, fullDate } from "@/lib/format";

const KINDS = {
  "": "All activity",
  "user.": "Roles and accounts",
  "request.": "Access requests",
  "profile.": "Profile changes",
  "password.": "Password changes",
  "role.": "Roles",
  "connector.": "Connectors",
  "access.": "Source access",
  "mcp.": "MCP tools",
} as const;

const b = (text: string | null) => <strong className="font-medium text-foreground">{text ?? "someone"}</strong>;

// One plain sentence per log entry.
function describe(a: Activity): ReactNode {
  const d = a.details as {
    before?: string[]; after?: string[]; value?: boolean; role?: string; note?: string | null;
    name?: string; kind?: string; source?: string; changed?: string[];
  };
  const list = (roles?: string[]) => (roles?.length ? roles.join(", ") : "admins only");
  const self = a.actor === a.target;
  switch (a.action) {
    case "user.roles": {
      const added = (d.after ?? []).filter((r) => !(d.before ?? []).includes(r));
      const removed = (d.before ?? []).filter((r) => !(d.after ?? []).includes(r));
      return (
        <>
          {b(a.actor)}{added.length > 0 && <> gave {b(a.target)} the {added.join(", ")} role{added.length > 1 ? "s" : ""}</>}
          {added.length > 0 && removed.length > 0 && " and"}
          {removed.length > 0 && <> removed {removed.join(", ")} from {added.length ? "them" : b(a.target)}</>}
        </>
      );
    }
    case "user.active":
      return <>{b(a.actor)} {d.value ? "reactivated" : "deactivated"} {b(a.target)}</>;
    case "user.admin":
      return <>{b(a.actor)} {d.value ? "made" : "removed admin from"} {b(a.target)}{d.value ? " an admin" : ""}</>;
    case "request.created":
      return <>{b(a.actor)} requested the {d.role} role</>;
    case "request.approved":
    case "request.denied":
      return (
        <>
          {b(a.actor)} {a.action === "request.approved" ? "approved" : "denied"} {b(a.target)}&apos;s request for {d.role}
          {d.note && <span className="text-muted"> · &ldquo;{d.note}&rdquo;</span>}
        </>
      );
    case "request.cancelled":
      return <>{b(a.actor)} cancelled their request for {d.role}</>;
    case "profile.updated":
      return self ? <>{b(a.actor)} updated their profile</> : <>{b(a.actor)} updated {b(a.target)}&apos;s profile</>;
    case "password.changed":
      return <>{b(a.actor)} changed their password</>;
    case "role.added":
      return <>{b(a.actor)} added the {d.role} role</>;
    case "role.removed":
      return <>{b(a.actor)} removed the {d.role} role</>;
    case "connector.added":
      return <>{b(a.actor ?? "Setup script")} connected {b(d.name ?? "")}</>;
    case "connector.synced":
      return <>{b(a.actor)} started a sync of {b(d.name ?? "")}</>;
    case "mcp.added":
      return <>{b(a.actor)} connected the {b(d.name ?? "")} MCP server</>;
    case "mcp.removed":
      return <>{b(a.actor)} removed the {b(d.name ?? "")} MCP server</>;
    case "mcp.updated":
      return <>{b(a.actor)} changed {(d.changed ?? []).join(", ")} on the {b(d.name ?? "")} MCP server</>;
    case "mcp.tool_on":
      return <>{b(a.actor)} turned on {b(d.name ?? "")}</>;
    case "mcp.tool_off":
      return <>{b(a.actor)} turned off {b(d.name ?? "")}</>;
    case "mcp.tool_roles":
      return <>{b(a.actor)} set who can use {b(d.name ?? "")}: {list(d.after)}</>;
    case "connector.removed":
      return <>{b(a.actor)} removed the {b(d.name ?? "")} connector</>;
    case "connector.updated":
      return <>{b(a.actor)} changed {(d.changed ?? []).join(", ").replaceAll("_", " ")} on {b(d.name ?? "")}</>;
    case "access.changed":
      return <>{b(a.actor)} set who can read {b(d.source ?? "")}: {list(d.before)} → {list(d.after)}</>;
    default:
      return <>{b(a.actor)} · {a.action}</>;
  }
}

const DOT: Record<string, string> = {
  "request.approved": "bg-emerald-500",
  "request.denied": "bg-red-500",
  "user.active": "bg-amber-500",
  "user.roles": "bg-brand",
  "access.changed": "bg-brand",
  "connector.added": "bg-emerald-500",
  "connector.removed": "bg-red-500",
};

export function ActivityTab({ items }: { items: Activity[] }) {
  const [kind, setKind] = useState<keyof typeof KINDS>("");

  const days = useMemo(() => {
    const groups: { day: string; items: Activity[] }[] = [];
    for (const item of items.filter((a) => a.action.startsWith(kind))) {
      const day = dayLabel(item.created_at);
      if (groups.at(-1)?.day !== day) groups.push({ day, items: [] });
      groups.at(-1)!.items.push(item);
    }
    return groups;
  }, [items, kind]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <p className="text-sm text-muted">Every change to people, roles and requests, newest first.</p>
        <select value={kind} onChange={(e) => setKind(e.target.value as keyof typeof KINDS)} aria-label="Filter activity"
          className="rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-brand">
          {Object.entries(KINDS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </div>

      {days.length === 0 ? (
        <EmptyState icon="activity" title="No activity yet">Role changes, requests and account changes are recorded here.</EmptyState>
      ) : (
        <div className="space-y-6">
          {days.map(({ day, items: dayItems }) => (
            <section key={day}>
              <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">{day}</h3>
              <ol className="divide-y divide-border rounded-2xl border border-border bg-surface shadow-sm">
                {dayItems.map((a) => (
                  <li key={a.id} className="flex items-start gap-3 px-4 py-3 text-sm sm:px-5">
                    <div className="relative">
                      <Avatar name={a.actor ?? "?"} size="sm" />
                      <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-surface ${DOT[a.action] ?? "bg-navy/30"}`} />
                    </div>
                    <p className="min-w-0 flex-1 pt-1.5 text-muted">{describe(a)}</p>
                    <time dateTime={a.created_at} title={fullDate(a.created_at)} className="shrink-0 pt-1.5 text-xs tabular-nums text-muted">
                      {new Date(a.created_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                    </time>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
