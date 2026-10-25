"use client";

import { useEffect, useState } from "react";
import { EmptyState, ErrorNote, Pill } from "@/components/admin/parts";
import { QueryInspector } from "@/components/admin/query-inspector";
import { api, type Usage, type UsageTotals } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";

const money = (usd: number) => (usd < 0.01 && usd > 0 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`);
const number = (n: number) => n.toLocaleString();

function Totals({ label, t }: { label: string; t: UsageTotals }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5 shadow-sm">
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{number(t.questions)}</div>
      <div className="text-xs text-muted">questions</div>
      <dl className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
        <div><dt className="text-muted">Tokens</dt><dd className="font-medium tabular-nums">{number(t.tokens)}</dd></div>
        <div><dt className="text-muted">Cost</dt><dd className="font-medium tabular-nums">{money(t.cost_usd)}</dd></div>
        <div><dt className="text-muted">Avg time</dt><dd className="font-medium tabular-nums">{t.avg_seconds.toFixed(1)} s</dd></div>
      </dl>
      {t.not_found > 0 && <p className="mt-2 text-xs text-muted">{t.not_found} answered &ldquo;couldn&apos;t find&rdquo;</p>}
    </div>
  );
}

// Questions, tokens and cost from GitMore's own log, kept even while Langfuse is off.
export function UsageTab() {
  const [usage, setUsage] = useState<Usage | null>(null);
  const [inspecting, setInspecting] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.usage().then(setUsage).catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorNote message={error} />;
  if (!usage) return <div className="h-40 animate-pulse rounded-2xl bg-navy/5" />;

  return (
    <div className="space-y-8">
      <p className="text-sm text-muted">
        Every question is recorded here with its tokens, cost and time, even when Langfuse is off. Click a question to
        inspect it: the route, what was searched and every chunk found with its scores.
      </p>

      <div className="grid gap-4 md:grid-cols-3">
        <Totals label="Today" t={usage.today} />
        <Totals label="Last 7 days" t={usage.last_7_days} />
        <Totals label="All time" t={usage.all_time} />
      </div>

      {usage.top_users.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold">Most active</h2>
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
            {usage.top_users.map((u) => (
              <li key={u.name} className="rounded-xl border border-border bg-surface px-4 py-3 text-sm">
                <div className="truncate font-medium">{u.name}</div>
                <div className="text-xs text-muted tabular-nums">{u.questions} questions · {money(u.cost_usd)}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold">Recent questions</h2>
        {usage.recent.length === 0 ? (
          <EmptyState icon="activity" title="No questions yet">Questions asked in the chat appear here.</EmptyState>
        ) : (
          <div className="overflow-x-auto rounded-2xl border border-border bg-surface shadow-sm">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] font-semibold uppercase tracking-wider text-muted">
                  <th className="px-5 py-3">Question</th>
                  <th className="px-4 py-3">Asked by</th>
                  <th className="px-4 py-3 text-right">Tokens</th>
                  <th className="px-4 py-3 text-right">Cost</th>
                  <th className="px-4 py-3 text-right">Time</th>
                  <th className="px-4 py-3">When</th>
                  <th className="px-4 py-3">Trace</th>
                </tr>
              </thead>
              <tbody>
                {usage.recent.map((r) => (
                  <tr key={r.id} onClick={() => setInspecting(r.id)}
                    className="cursor-pointer border-b border-border last:border-0 hover:bg-navy/[0.03]">
                    <td className="max-w-[22rem] px-5 py-3">
                      <button onClick={(e) => { e.stopPropagation(); setInspecting(r.id); }}
                        className="block max-w-full truncate text-left font-medium hover:text-brand-strong" title={r.question}>
                        {r.question}
                      </button>
                      {r.route && <span className="mr-1 text-[11px] text-muted">{r.route}</span>}
                      {!r.found && <Pill tone="warn">couldn&apos;t find</Pill>}
                    </td>
                    <td className="px-4 py-3 text-muted">{r.user ?? "deleted user"}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{number(r.tokens)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{money(r.cost_usd)}</td>
                    <td className="px-4 py-3 text-right tabular-nums">{r.seconds.toFixed(1)} s</td>
                    <td className="px-4 py-3 text-xs text-muted" title={fullDate(r.created_at)}>{timeAgo(r.created_at)}</td>
                    <td className="px-4 py-3">
                      {r.trace_url
                        ? <a href={r.trace_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                            className="text-brand-strong hover:underline">Open</a>
                        : <span className="text-xs text-muted">not traced</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {inspecting !== null && <QueryInspector id={inspecting} onClose={() => setInspecting(null)} />}
    </div>
  );
}
