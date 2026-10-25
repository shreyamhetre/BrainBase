"use client";

import { useEffect, useState, type FormEvent } from "react";
import { ErrorNote } from "@/components/admin/parts";
import { Icon } from "@/components/icons";
import { api, type LibraryDocument } from "@/lib/api";

const input = "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/15";

// Add a document: upload a PDF or Word file (choose who can read it), or link a file in GitLab
// (its access comes from its project). It is searchable and cited as soon as it's added.
export function AddDocument({ shareable, defaultRoles, onAdded, onClose }: {
  shareable: string[];
  defaultRoles: string[];
  onAdded: (doc: LibraryDocument) => void;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<"file" | "link">("file");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [roles, setRoles] = useState<string[]>(defaultRoles);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onClose]);

  function toggle(role: string) {
    if (role === "all") return setRoles(roles.includes("all") ? [] : ["all"]);
    const base = roles.filter((r) => r !== "all");
    setRoles(base.includes(role) ? base.filter((r) => r !== role) : [...base, role]);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      onAdded(mode === "file" ? await api.uploadDocument(file!, roles, title) : await api.linkDocument(url, title));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add the document");
      setBusy(false);
    }
  }

  const ready = mode === "file" ? !!file && roles.length > 0 : url.trim().length > 10;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4" onClick={() => !busy && onClose()}>
      <form role="dialog" aria-modal="true" aria-labelledby="add-doc" onSubmit={submit} onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-border bg-surface p-6 shadow-xl">
        <h2 id="add-doc" className="text-lg font-semibold">Add a document</h2>
        <p className="mt-1 text-sm text-muted">GitMore reads it, and it&apos;s searchable and cited right away, only for the people who can read it.</p>

        <div role="tablist" className="mt-5 grid grid-cols-2 gap-2">
          {([["file", "upload", "Upload a file", "PDF or Word"], ["link", "link", "Link a GitLab file", "Markdown, text, PDF or Word"]] as const)
            .map(([id, icon, label, hint]) => (
              <button key={id} type="button" role="tab" aria-selected={mode === id} onClick={() => { setMode(id); setError(""); }}
                className={`flex items-center gap-3 rounded-xl border p-3 text-left text-sm transition ${
                  mode === id ? "border-brand ring-2 ring-brand/20" : "border-border hover:border-brand/50"}`}>
                <Icon name={icon} className="h-5 w-5 shrink-0 text-muted" />
                <span><span className="block font-medium">{label}</span><span className="text-xs text-muted">{hint}</span></span>
              </button>
            ))}
        </div>

        <div className="mt-5 space-y-4">
          {mode === "file" ? (
            <>
              <label className="block space-y-1">
                <span className="text-sm font-medium">File</span>
                <input type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand/10 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-strong hover:file:bg-brand/20" />
                <span className="block text-xs text-muted">Up to 10 MB. Scanned PDFs without text can&apos;t be read.</span>
              </label>
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">Who can read it</legend>
                <div className="flex flex-wrap gap-2">
                  {shareable.map((r) => {
                    const on = roles.includes(r);
                    return (
                      <button key={r} type="button" aria-pressed={on} onClick={() => toggle(r)}
                        className={`rounded-full border px-3 py-1 text-sm transition ${
                          on ? "border-brand bg-brand text-white" : "border-border text-muted hover:border-brand/50"}`}>
                        {r === "all" ? "Everyone" : r}
                      </button>
                    );
                  })}
                </div>
                <p className="text-xs text-muted">You can share with everyone or with roles you have.</p>
              </fieldset>
            </>
          ) : (
            <label className="block space-y-1">
              <span className="text-sm font-medium">Link to a file in GitLab</span>
              <input className={`${input} font-mono`} type="url" value={url} onChange={(e) => setUrl(e.target.value)}
                placeholder="https://gitlab.com/<group>/<project>/-/blob/main/docs/policy.md" />
              <span className="block text-xs text-muted">
                A file in your connected GitLab group. It gets the same access as its project, and you can refresh it later.
              </span>
            </label>
          )}
          <label className="block space-y-1">
            <span className="text-sm font-medium">Title <span className="font-normal text-muted">(optional)</span></span>
            <input className={input} value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200}
              placeholder="Taken from the document when empty" />
          </label>
        </div>

        <div className="mt-5"><ErrorNote message={error} /></div>

        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={busy} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
            Cancel
          </button>
          <button disabled={busy || !ready} className="rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-50">
            {busy ? "Reading and indexing…" : "Add document"}
          </button>
        </div>
      </form>
    </div>
  );
}
