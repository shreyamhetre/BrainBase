"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icon, type IconName } from "@/components/icons";

// "all" marks content everyone can read; an empty list means "nobody but admins" for sources
// and "handbook only" for people.
export const rolesText = (roles: string[], empty = "Handbook only") =>
  roles.length ? roles.map((r) => (r === "all" ? "everyone" : r)).join(", ") : empty;

// On/off switch. The parent decides what happens; the switch itself never flips on its own.
export function Switch({ on, disabled, label, onToggle }: { on: boolean; disabled?: boolean; label: string; onToggle: () => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={onToggle}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition disabled:cursor-not-allowed disabled:opacity-50 ${
        on ? "bg-brand" : "bg-navy/20"}`}>
      <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition ${on ? "translate-x-[18px]" : "translate-x-0.5"}`} />
    </button>
  );
}

const PILL = {
  neutral: "bg-navy/10 text-muted",
  brand: "bg-brand/10 text-brand-strong",
  good: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  bad: "bg-red-500/10 text-red-700 dark:text-red-400",
  warn: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
};

export function Pill({ tone = "neutral", children }: { tone?: keyof typeof PILL; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${PILL[tone]}`}>{children}</span>;
}

export function EmptyState({ icon, title, children }: { icon: IconName; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-border bg-surface px-6 py-14 text-center">
      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-brand/10 text-brand-strong">
        <Icon name={icon} />
      </span>
      <h3 className="mt-3 text-sm font-semibold">{title}</h3>
      {children && <div className="mt-1 max-w-sm text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  if (!message) return null;
  return <p role="alert" className="mb-4 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-700 dark:text-red-400">{message}</p>;
}

// Multi-select roles dropdown. Picking a role doesn't change anything by itself:
// it calls onPick, and the page asks for confirmation before saving.
export function RolesDropdown({ value, roles, disabled, allRoles, emptyLabel, onPick }: {
  value: string[];
  roles: string[];
  disabled?: boolean;
  allRoles?: boolean;
  emptyLabel?: string;
  onPick: (role: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (allRoles) return <Pill tone="brand">All roles</Pill>;

  return (
    <div ref={box} className="relative w-full max-w-[15rem]">
      <button type="button" disabled={disabled} onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-1.5 text-left text-sm transition hover:border-brand/60 disabled:opacity-60">
        <span className={`truncate ${value.length ? "" : "text-muted"}`}>{rolesText(value, emptyLabel)}</span>
        <Icon name="chevron" className={`h-4 w-4 shrink-0 text-muted transition ${open ? "-rotate-90" : "rotate-90"}`} />
      </button>
      {open && (
        <ul role="listbox" aria-multiselectable="true"
          className="absolute left-0 z-30 mt-1 w-full min-w-44 rounded-lg border border-border bg-surface py-1 shadow-lg">
          {roles.map((role) => {
            const on = value.includes(role);
            return (
              <li key={role} role="option" aria-selected={on}>
                <button type="button" onClick={() => { setOpen(false); onPick(role); }}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-brand/10">
                  <span className={`flex h-4 w-4 items-center justify-center rounded border ${on ? "border-brand bg-brand text-white" : "border-border"}`}>
                    {on && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                  </span>
                  {role === "all" ? "everyone" : role}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
