"use client";

import { useEffect, useState } from "react";
import { ErrorNote, Pill } from "@/components/admin/parts";
import { AnswerText } from "@/components/answer-text";
import { Icon } from "@/components/icons";
import { api, type GateDetail, type UsageDetail } from "@/lib/api";
import { fullDate } from "@/lib/format";

const ROUTE: Record<string, { label: string; tone: "neutral" | "brand" | "good" | "warn" }> = {
  answer: { label: "Answer from sources", tone: "good" },
  action: { label: "Action proposed", tone: "brand" },
  choose: { label: "Explain or do it", tone: "brand" },
  clarify: { label: "Asked back", tone: "warn" },
  chat: { label: "Small talk", tone: "neutral" },
};

const SOURCE: Record<string, string> = { handbook: "Handbook", slack: "Slack", gitlab_issue: "Issue", gitlab_wiki: "Wiki",
  upload: "Document", gitlab_file: "GitLab file" };

const GATE: Record<GateDetail["outcome"], { label: string; tone: "good" | "warn" | "bad" | "neutral" }> = {
  passed: { label: "Enough evidence", tone: "good" },
  passed_after_retry: { label: "Enough after a retry", tone: "warn" },
  failed: { label: "Not enough: couldn't find", tone: "bad" },
  skipped: { label: "Gate skipped", tone: "neutral" },
};

const prob = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n.toFixed(2));

// What Jev read and decided, for each try (the first search, and the retry with a rewritten question)
function GateSection({ gate }: { gate: GateDetail }) {
  const outcome = GATE[gate.outcome];
  return (
    <Section title="Evidence gate (Jev)">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <Pill tone={outcome.tone}>{outcome.label}</Pill>
        <span>threshold {gate.threshold} · {gate.model} · {gate.jev_tokens.toLocaleString()} tokens · ${gate.jev_cost_usd.toFixed(6)}</span>
      </div>
      {gate.checks.map((c, i) => (
        <div key={i} className="rounded-xl border border-border p-3">
          <div className="flex flex-wrap items-baseline gap-2 text-sm">
            <span className="font-medium">{i === 0 ? "First search" : "Retry"}</span>
            {c.error ? <span className="text-xs text-red-700 dark:text-red-400">{c.error}</span> : (
              <span className="text-xs text-muted">
                enough evidence: <strong className={c.passed ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"}>
                  {prob(c.enough)}</strong>{c.sent.length ? "" : " (nothing found)"} · {c.seconds} s
              </span>
            )}
          </div>
          {i > 0 && <p className="mt-1 text-xs text-muted">Rewritten question: <span className="text-foreground">{c.question}</span></p>}
          {c.sent.length > 0 && (
            <ol className="mt-2 space-y-1 text-xs">
              {c.sent.map((s, n) => (
                <li key={s.n} className="flex gap-2">
                  <span className="w-10 shrink-0 font-semibold tabular-nums">{prob(c.per_source[n])}</span>
                  <span className="min-w-0 truncate" title={s.text}>[{s.n}] {s.title} <span className="text-muted">· {SOURCE[s.type] ?? s.type}{s.date ? ` · ${s.date}` : ""}</span></span>
                </li>
              ))}
            </ol>
          )}
        </div>
      ))}
      <p className="text-xs text-muted">
        Jev reads the question with the start of each source, and gives the probability that together they are enough to answer and that
        each source helps. Hover a source to see the text Jev read.
      </p>
    </Section>
  );
}

const score = (n: number | null, digits = 3) => (n === null || n === undefined ? "—" : n.toFixed(digits));

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted">{title}</h3>
      {children}
    </section>
  );
}

// Everything recorded about one message: who asked, the route, what was searched, every chunk
// found with its scores, and the answer. Opens from the Usage tab.
export function QueryInspector({ id, onClose }: { id: number; onClose: () => void }) {
  const [detail, setDetail] = useState<UsageDetail | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.usageDetail(id).then(setDetail).catch((e) => setError(e.message));
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [id, onClose]);

  const chunks = detail?.details.chunks ?? [];
  const route = detail?.route === "answer" && !detail.found ? { label: "Couldn't find", tone: "warn" as const }
    : detail?.route ? ROUTE[detail.route] : null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-labelledby="inspector-title" onClick={(e) => e.stopPropagation()}
        className="flex h-full w-full max-w-2xl flex-col border-l border-border bg-surface shadow-2xl">
        <header className="flex items-start gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">Query inspector</div>
            <h2 id="inspector-title" className="mt-1 text-base font-semibold leading-snug">{detail?.question ?? "…"}</h2>
            {detail && (
              <p className="mt-1 text-xs text-muted">
                {detail.user ?? "deleted user"} · {fullDate(detail.created_at)}
              </p>
            )}
          </div>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1.5 text-muted hover:bg-navy/5 hover:text-foreground">
            <Icon name="close" />
          </button>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <ErrorNote message={error} />
          {!detail && !error && <div className="h-40 animate-pulse rounded-xl bg-navy/5" />}

          {detail && (
            <>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ["Route", route ? <Pill key="r" tone={route.tone}>{route.label}</Pill> : <span key="r" className="text-xs text-muted">not recorded (asked before the inspector)</span>],
                  ["Tokens", `${(detail.prompt_tokens + detail.completion_tokens).toLocaleString()} (${detail.prompt_tokens.toLocaleString()} in)`],
                  ["Cost", `$${detail.cost_usd.toFixed(5)}`],
                  ["Time", `${detail.seconds.toFixed(1)} s`],
                ].map(([label, value]) => (
                  <div key={label as string} className="rounded-xl border border-border px-3 py-2">
                    <div className="text-[11px] text-muted">{label}</div>
                    <div className="mt-0.5 text-sm font-medium">{value}</div>
                  </div>
                ))}
              </div>

              {detail.search_question && detail.search_question !== detail.question && (
                <Section title="Searched for">
                  <p className="rounded-lg bg-navy/5 px-3 py-2 text-sm">{detail.search_question}</p>
                  <p className="text-xs text-muted">
                    {detail.details.gate?.checks.length === 2
                      ? "The first search didn't have enough evidence, so GPT rewrote the question and GitMore searched again."
                      : "The router rewrote the message so it stands on its own (a follow-up, or the facts an action needed)."}
                  </p>
                </Section>
              )}

              {detail.details.action && (
                <Section title="Action">
                  <p className="text-sm">
                    <span className="font-mono text-xs">{detail.details.action.tool}</span> via {detail.details.action.server}
                    {detail.details.action.target ? ` · ${detail.details.action.target}` : ""}
                  </p>
                  <p className="text-sm text-muted">{detail.details.action.summary}</p>
                </Section>
              )}

              {detail.details.gate && <GateSection gate={detail.details.gate} />}

              <Section title={`Chunks found (${chunks.length})`}>
                {detail.route === null ? (
                  <p className="text-sm text-muted">Details weren&apos;t recorded for questions asked before the inspector was added.</p>
                ) : chunks.length === 0 ? (
                  <p className="text-sm text-muted">No search for this message{detail.route === "chat" || detail.route === "clarify" ? " (it didn't need one)" : ""}.</p>
                ) : (
                  <ol className="space-y-2">
                    {chunks.map((c) => (
                      <li key={c.rank} className={`rounded-xl border p-3 ${c.cited ? "border-brand/50 bg-brand/[0.03]" : "border-border"}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-navy/10 px-1 text-[11px] font-semibold">{c.rank}</span>
                          <a href={c.link} target="_blank" rel="noreferrer" className="min-w-0 flex-1 truncate text-sm font-medium hover:underline">
                            {c.heading_path}
                          </a>
                          <Pill>{SOURCE[c.source] ?? c.source}</Pill>
                          {c.cited ? <Pill tone="brand">cited</Pill> : <span className="text-[11px] text-muted">not cited</span>}
                        </div>
                        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs tabular-nums sm:grid-cols-4">
                          <div><dt className="text-muted">Rerank</dt><dd className="font-semibold">{score(c.rerank_score)}</dd></div>
                          <div><dt className="text-muted">Fusion (RRF)</dt><dd>{score(c.rrf_score, 4)}</dd></div>
                          <div><dt className="text-muted">Vector</dt><dd>{c.vector_rank ? `#${c.vector_rank} · ${score(c.vector_score)}` : "—"}</dd></div>
                          <div><dt className="text-muted">Keyword</dt><dd>{c.keyword_rank ? `#${c.keyword_rank} · ${score(c.keyword_score)}` : "—"}</dd></div>
                        </dl>
                        <p className="mt-2 line-clamp-3 text-xs text-muted">{c.preview}</p>
                      </li>
                    ))}
                  </ol>
                )}
                {chunks.length > 0 && (
                  <p className="text-xs text-muted">
                    Vector and keyword search each return their best matches, fusion (RRF) merges the two lists, and the reranker scores the
                    top of the merged list (0 to 1); the best {chunks.length} go to the model.
                  </p>
                )}
              </Section>

              <Section title="Reply">
                <div className="rounded-xl border border-border p-4 text-sm">
                  <AnswerText text={detail.answer.replace(/^\[(action|choose|clarify|chat)\] /, "")} onCite={() => {}} />
                </div>
              </Section>

              {detail.trace_url && (
                <a href={detail.trace_url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium hover:border-brand/60">
                  Open the full trace in Langfuse <Icon name="chevron" className="h-4 w-4 text-muted" />
                </a>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}
