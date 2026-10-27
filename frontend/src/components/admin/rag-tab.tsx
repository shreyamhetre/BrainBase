"use client";

import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { ErrorNote, Pill } from "@/components/admin/parts";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { api, type RagSettings, type RagSettingsResponse } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";

const LABELS: Record<keyof RagSettings, string> = {
  candidates_per_search: "Results per search",
  rerank_pool: "Rerank pool",
  final_k: "Sources per answer",
  llm_model: "Model",
  price_input_per_m: "Input price",
  price_output_per_m: "Output price",
  answer_length: "Answer length",
  handbook_core_sections: "Sections always kept",
  handbook_max_age_days: "Keep pages changed in the last",
};

const field = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15";

function Row({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <div className="grid gap-2 py-4 sm:grid-cols-[14rem_1fr] sm:gap-6">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="mt-0.5 text-xs text-muted">{hint}</div>
      </div>
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function Card({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface px-5 py-2 shadow-sm">
      <div className="border-b border-border py-4">
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="mt-0.5 text-xs text-muted">{description}</p>
      </div>
      <div className="divide-y divide-border">{children}</div>
    </section>
  );
}

const show = (key: keyof RagSettings, v: unknown) =>
  Array.isArray(v) ? (v.length ? v.join(", ") : "none") : key.startsWith("price") ? `$${v} / M tokens` : String(v);

// RAG settings: search and answers apply to the next message; handbook rules on the next refresh.
export function RagTab() {
  const [data, setData] = useState<RagSettingsResponse | null>(null);
  const [draft, setDraft] = useState<RagSettings | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [refreshAsk, setRefreshAsk] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => api.ragSettings().then((r) => { setData(r); setDraft(r.settings); }).catch((e) => setError(e.message)), []);
  useEffect(() => { load(); }, [load]);

  // While the handbook refreshes, check its progress every 3 seconds
  const running = data?.handbook.job.state === "running";
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => api.ragSettings().then((r) => setData((d) => d && { ...d, handbook: r.handbook, sections: r.sections })), 3000);
    return () => clearInterval(timer);
  }, [running]);

  const changes = useMemo(() => {
    if (!data || !draft) return {};
    return Object.fromEntries(Object.entries(draft).filter(([k, v]) =>
      JSON.stringify(v) !== JSON.stringify(data.settings[k as keyof RagSettings]))) as Partial<RagSettings>;
  }, [data, draft]);
  const dirty = Object.keys(changes).length > 0;

  async function save() {
    setConfirming(false);
    setError("");
    try {
      const r = await api.saveRagSettings(changes);
      setData(r);
      setDraft(r.settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't save the settings");
    }
  }

  async function refresh() {
    setRefreshAsk(false);
    setError("");
    try {
      await api.refreshHandbook();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't start the refresh");
    }
  }

  if (!data || !draft) return error ? <ErrorNote message={error} /> : <div className="h-40 animate-pulse rounded-2xl bg-navy/5" />;

  const set = <K extends keyof RagSettings>(key: K, value: RagSettings[K]) => setDraft({ ...draft, [key]: value });
  const num = (key: keyof RagSettings) => (
    <input type="number" className={`${field} max-w-[10rem] tabular-nums`} value={draft[key] as number}
      min={data.limits[key]?.[0]} max={data.limits[key]?.[1]} step={key.startsWith("price") ? 0.01 : 1}
      onChange={(e) => set(key, Number(e.target.value) as never)} />
  );
  const range = (key: keyof RagSettings) => data.limits[key] ? `${data.limits[key][0]}–${data.limits[key][1]}` : "";
  const job = data.handbook.job;
  const core = new Set(draft.handbook_core_sections);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm sm:flex-row sm:items-center">
        <Icon name="activity" className="h-5 w-5 shrink-0 text-amber-600" />
        <p className="flex-1 text-muted">
          Search and answer settings apply to the next message. After changing them, run the quick evaluation
          (<code className="text-xs">python backend/scripts/evaluate_access.py --quick</code>) to check quality and permissions.
        </p>
      </div>
      <ErrorNote message={error} />

      <Card title="Search" description="How many results each step keeps. More results can find more, but are slower and cost more tokens.">
        <Row label={LABELS.candidates_per_search} hint={`Vector and keyword search each return this many (${range("candidates_per_search")}). Default ${data.defaults.candidates_per_search}.`}>
          {num("candidates_per_search")}
        </Row>
        <Row label={LABELS.rerank_pool} hint={`The best fused results the reranker reads closely (${range("rerank_pool")}). Default ${data.defaults.rerank_pool}.`}>
          {num("rerank_pool")}
        </Row>
        <Row label={LABELS.final_k} hint={`Sources passed to the model and cited (${range("final_k")}). Default ${data.defaults.final_k}.`}>
          {num("final_k")}
        </Row>
      </Card>

      <Card title="Answers" description="The model that routes messages and writes answers, and what it costs.">
        <Row label={LABELS.llm_model} hint="Any model your API key can use, e.g. gpt-4o-mini or gpt-4o.">
          <input className={`${field} max-w-xs font-mono`} value={draft.llm_model} onChange={(e) => set("llm_model", e.target.value)} />
        </Row>
        <Row label="Price per million tokens" hint="Used for cost in Usage. Set them to your model's list prices.">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <label className="flex items-center gap-2">Input $ {num("price_input_per_m")}</label>
            <label className="flex items-center gap-2">Output $ {num("price_output_per_m")}</label>
          </div>
        </Row>
        <Row label={LABELS.answer_length} hint="How much the model writes. Citations stay the same.">
          <div role="radiogroup" className="flex flex-wrap gap-2">
            {Object.keys(data.answer_lengths).map((length) => (
              <button key={length} type="button" role="radio" aria-checked={draft.answer_length === length}
                onClick={() => set("answer_length", length)} title={data.answer_lengths[length]}
                className={`rounded-lg border px-3 py-1.5 text-sm capitalize ${
                  draft.answer_length === length ? "border-brand bg-brand text-white" : "border-border text-muted hover:border-brand/50"}`}>
                {length}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted">{data.answer_lengths[draft.answer_length]}</p>
        </Row>
      </Card>

      <Card title="GitLab handbook" description="Which handbook pages are indexed. Rules apply when the handbook is refreshed.">
        <Row label={LABELS.handbook_max_age_days} hint={`Pages changed in this many days are kept (${range("handbook_max_age_days")}; the copy has one year of history).`}>
          <div className="flex items-center gap-2 text-sm">{num("handbook_max_age_days")} days</div>
        </Row>
        <Row label={LABELS.handbook_core_sections} hint="Kept whatever their age: core policy sections. Click to add or remove.">
          <div className="flex flex-wrap gap-1.5">
            {data.sections.map((s) => {
              const on = core.has(s.name);
              return (
                <button key={s.name} type="button" aria-pressed={on} title={`${s.pages} pages in the handbook, ${s.indexed} indexed now`}
                  onClick={() => set("handbook_core_sections", on ? draft.handbook_core_sections.filter((x) => x !== s.name) : [...draft.handbook_core_sections, s.name])}
                  className={`rounded-full border px-2.5 py-1 text-xs ${on ? "border-brand bg-brand text-white" : "border-border text-muted hover:border-brand/50"}`}>
                  {s.name} <span className="opacity-70">{s.indexed}/{s.pages}</span>
                </button>
              );
            })}
          </div>
          <p className="mt-2 text-xs text-muted">Numbers: pages indexed now / pages in the handbook.</p>
        </Row>
        <Row label="Refresh" hint="Pulls the latest pages from GitLab and re-indexes what changed. The first refresh after a while can take several minutes.">
          <div className="space-y-2 text-sm">
            <p className="text-muted">
              <span className="font-medium text-foreground">{data.handbook.indexed_pages.toLocaleString()}</span> pages indexed
              {job.state === "done" && job.finished_at && <> · last refreshed <span title={fullDate(job.finished_at)}>{timeAgo(job.finished_at)}</span></>}
            </p>
            {job.state === "running" && (
              <p className="flex items-center gap-2 text-brand-strong"><span className="h-2 w-2 animate-pulse rounded-full bg-brand" />{job.step ?? "Working…"}</p>
            )}
            {job.state === "done" && job.stats && (
              <p className="text-xs text-muted">
                Last refresh: {job.stats.pages} pages checked, {job.stats.embedded_pages} new or changed, {job.stats.unchanged} unchanged,
                {" "}{job.stats.deleted} removed · {job.stats.minutes} min
              </p>
            )}
            {job.state === "error" && <p className="text-xs text-red-700 dark:text-red-400">Last refresh failed: {job.error}</p>}
            <button disabled={running || dirty} onClick={() => setRefreshAsk(true)}
              title={dirty ? "Save your changes first" : undefined}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60 disabled:opacity-50">
              <Icon name="activity" className="h-4 w-4 text-muted" /> {running ? "Refreshing…" : "Refresh handbook"}
            </button>
          </div>
        </Row>
      </Card>

      <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-border bg-background/90 py-3 backdrop-blur">
        {saved && <span className="text-sm text-emerald-700 dark:text-emerald-400">Saved</span>}
        {dirty && <Pill tone="warn">{Object.keys(changes).length} unsaved {Object.keys(changes).length === 1 ? "change" : "changes"}</Pill>}
        <button disabled={!dirty} onClick={() => setDraft(data.settings)} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground disabled:opacity-50">
          Discard
        </button>
        <button disabled={!dirty} onClick={() => setConfirming(true)}
          className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-50">
          Save changes
        </button>
      </div>

      {confirming && (
        <ConfirmDialog title="Save these settings?" yesLabel="Save" noLabel="Cancel" onYes={save} onNo={() => setConfirming(false)}>
          <ul className="space-y-1">
            {Object.entries(changes).map(([k, v]) => (
              <li key={k}><span className="font-medium text-foreground">{LABELS[k as keyof RagSettings]}:</span>{" "}
                {show(k as keyof RagSettings, data.settings[k as keyof RagSettings])} → {show(k as keyof RagSettings, v)}</li>
            ))}
          </ul>
        </ConfirmDialog>
      )}
      {refreshAsk && (
        <ConfirmDialog title="Refresh the handbook now?" yesLabel="Refresh" noLabel="Cancel" onYes={refresh} onNo={() => setRefreshAsk(false)}>
          GitMore pulls the latest pages from GitLab, applies the rules above and re-indexes what changed. Answers keep working meanwhile.
        </ConfirmDialog>
      )}
    </div>
  );
}
