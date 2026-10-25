"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { EmptyState, ErrorNote, Pill, rolesText } from "@/components/admin/parts";
import { PageHeader } from "@/components/app-shell";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { AddDocument } from "@/components/knowledge/add-document";
import { api, type Library, type LibraryDocument } from "@/lib/api";
import { fullDate, timeAgo } from "@/lib/format";
import { useUser } from "@/lib/user-context";

const KIND: Record<string, string> = { pdf: "PDF", word: "Word", text: "Text", gitlab_file: "GitLab file" };
const SOURCE_COLOR: Record<string, string> = {
  handbook: "bg-navy text-surface", slack: "bg-[#4a154b] text-white", gitlab_issue: "bg-[#fc6d26] text-white",
  gitlab_wiki: "bg-[#fc6d26] text-white",
};

// What GitMore knows, for this person: the sources it searches and the documents people added.
// Everything listed here is something you can read; documents you can't read don't appear.
export default function KnowledgePage() {
  const { user } = useUser();
  const [library, setLibrary] = useState<Library | null>(null);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<LibraryDocument | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [error, setError] = useState("");
  const replaceInput = useRef<HTMLInputElement>(null);
  const replacing = useRef<LibraryDocument | null>(null);

  useEffect(() => {
    if (user) api.library().then(setLibrary).catch((e) => setError(e.message));
  }, [user]);

  const docs = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (library?.documents ?? []).filter((d) =>
      !q || [d.title, d.file_name ?? "", d.added_by ?? "", KIND[d.kind] ?? ""].join(" ").toLowerCase().includes(q));
  }, [library, query]);

  async function run(id: number, action: () => Promise<LibraryDocument | void>) {
    setBusy(id);
    setError("");
    try {
      const updated = await action();
      setLibrary((lib) => lib && {
        ...lib,
        documents: updated ? lib.documents.map((d) => (d.id === id ? updated : d)) : lib.documents.filter((d) => d.id !== id),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(null);
    }
  }

  const defaultRoles = user?.is_admin ? ["all"] : (user?.roles.length ? [user.roles[0]] : ["all"]);

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="Knowledge"
        description="Everything GitMore searches for you: company sources and the documents people added. You only see what you can read."
        actions={library?.can_add && (
          <button onClick={() => setAdding(true)}
            className="inline-flex items-center gap-2 self-start rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong">
            <Icon name="plus" className="h-4 w-4" /> Add document
          </button>
        )} />
      <ErrorNote message={error} />

      {library === null && !error && <div className="h-32 animate-pulse rounded-2xl bg-navy/5" />}

      {library && (
        <>
          <section>
            <h2 className="mb-3 text-sm font-semibold">Sources</h2>
            <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {library.sources.map((s) => (
                <li key={s.source} className="flex items-center gap-3 rounded-2xl border border-border bg-surface p-4 shadow-sm">
                  <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${SOURCE_COLOR[s.source] ?? "bg-navy/10 text-navy"}`}>
                    <Icon name={s.source === "handbook" ? "book" : s.source === "slack" ? "chat" : "plug"} className="h-5 w-5" />
                  </span>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">{s.name}</div>
                    <div className="text-xs text-muted tabular-nums">
                      {s.documents.toLocaleString()} {s.documents === 1 ? "document" : "documents"}
                      {s.last_updated && ` · updated ${timeAgo(s.last_updated)}`}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted">Sources sync on their own; admins manage them on the Connectors page.</p>
          </section>

          <section className="mt-8">
            <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-sm font-semibold">Added documents <span className="font-normal text-muted">({library.documents.length})</span></h2>
              {library.documents.length > 0 && (
                <label className="relative sm:w-64">
                  <span className="sr-only">Search documents</span>
                  <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                  <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by title, file or person"
                    className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-brand" />
                </label>
              )}
            </div>

            {library.documents.length === 0 ? (
              <EmptyState icon="book" title="No documents added yet">
                {library.can_add
                  ? "Add a policy, guide or plan as a PDF or Word file, or link a file in GitLab. GitMore can answer from it right away."
                  : "When someone adds a document you can read, it appears here. Ask an admin if your role should be able to add documents."}
              </EmptyState>
            ) : (
              <ul className="divide-y divide-border rounded-2xl border border-border bg-surface shadow-sm">
                {docs.map((d) => (
                  <li key={d.id} className={`flex flex-col gap-3 px-5 py-4 md:flex-row md:items-center ${busy === d.id ? "opacity-50" : ""}`}>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <a href={d.url} target="_blank" rel="noreferrer" className="truncate font-medium hover:text-brand-strong hover:underline">{d.title}</a>
                        <Pill>{KIND[d.kind] ?? d.kind}</Pill>
                      </div>
                      <p className="mt-1 text-xs text-muted">
                        Readable by <span className="text-foreground">{rolesText(d.allowed_roles, "admins only")}</span>
                        {" · "}added by {d.added_by ?? "someone"} <span title={fullDate(d.added_at)}>{timeAgo(d.added_at)}</span>
                        {d.file_name && ` · ${d.file_name}`}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <a href={d.url} target="_blank" rel="noreferrer"
                        className="rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">Open</a>
                      {d.can_manage && d.kind === "gitlab_file" && (
                        <button disabled={busy !== null} onClick={() => run(d.id, () => api.refreshDocument(d.id))}
                          className="rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">Refresh</button>
                      )}
                      {d.can_manage && d.kind !== "gitlab_file" && (
                        <button disabled={busy !== null} onClick={() => { replacing.current = d; replaceInput.current?.click(); }}
                          className="rounded-lg border border-border px-3 py-1.5 text-sm hover:border-brand/60">Replace</button>
                      )}
                      {d.can_manage && (
                        <button disabled={busy !== null} onClick={() => setRemoving(d)}
                          className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-red-500/10 hover:text-red-600">Remove</button>
                      )}
                    </div>
                  </li>
                ))}
                {docs.length === 0 && <li className="px-5 py-8 text-center text-sm text-muted">No document matches.</li>}
              </ul>
            )}
          </section>
        </>
      )}

      <input ref={replaceInput} type="file" accept=".pdf,.docx" className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          const doc = replacing.current;
          e.target.value = "";
          if (file && doc) run(doc.id, () => api.replaceDocument(doc.id, file));
        }} />

      {adding && library && (
        <AddDocument shareable={library.shareable_roles} defaultRoles={defaultRoles} onClose={() => setAdding(false)}
          onAdded={(doc) => { setLibrary({ ...library, documents: [doc, ...library.documents] }); setAdding(false); }} />
      )}

      {removing && (
        <ConfirmDialog title={`Remove "${removing.title}"?`} yesLabel="Remove" noLabel="Cancel" tone="danger"
          onYes={() => { const d = removing; setRemoving(null); run(d.id, () => api.removeDocument(d.id)); }}
          onNo={() => setRemoving(null)}>
          GitMore stops answering from it straight away. {removing.kind === "gitlab_file" ? "The file stays in GitLab." : "The uploaded file is deleted."}
        </ConfirmDialog>
      )}
    </main>
  );
}
