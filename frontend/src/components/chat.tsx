"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ActionCard } from "@/components/action-card";
import { AnswerText } from "@/components/answer-text";
import { api, ApiError, CHATS_CHANGED, NEW_CHAT, type AskResponse, type Conversation, type Source } from "@/lib/api";
import { useUser } from "@/lib/user-context";

type Turn = {
  id: number;
  question: string;
  response?: AskResponse;
  error?: string;
};

const EXAMPLES = [
  "How many weeks of parental leave do I get?",
  "How does paid time off work at GitLab?",
  "What are GitLab's core values?",
  "How do I report a security incident?",
];

const SOURCE_LABEL: Record<string, string> = {
  handbook: "Handbook",
  slack: "Slack",
  gitlab_issue: "Issue",
  gitlab_wiki: "Wiki",
};

function SourceCard({ source, turnId, highlighted }: { source: Source; turnId: number; highlighted: boolean }) {
  const crumbs = source.heading_path.split(" > ");
  return (
    <a
      id={`src-${turnId}-${source.number}`}
      href={source.link}
      target="_blank"
      rel="noreferrer"
      className={`block rounded-xl border p-3 text-sm transition hover:border-brand/60 ${
        highlighted ? "border-brand bg-brand/5 ring-2 ring-brand/20" : "border-border bg-surface"
      } ${source.cited ? "" : "opacity-70"}`}
    >
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1 text-[11px] font-semibold ${
          source.cited ? "bg-brand/15 text-brand-strong" : "bg-navy/10 text-muted"}`}>
          {source.number}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate font-medium">{crumbs[crumbs.length - 1]}</div>
          {/* Handbook: the page path. Slack threads and issues have no path; their title is already the heading. */}
          {(crumbs.length > 1 || source.title !== crumbs[0]) && (
            <div className="truncate text-xs text-muted">{crumbs.slice(0, -1).join(" › ") || source.title}</div>
          )}
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
            <span className="rounded bg-navy/10 px-1.5 py-0.5">{SOURCE_LABEL[source.source] ?? source.source}</span>
            {source.updated_at && <span>updated {source.updated_at}</span>}
            {source.status && (
              <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-amber-700 dark:text-amber-400">
                design doc: {source.status}
              </span>
            )}
            {!source.cited && <span>not cited</span>}
          </div>
        </div>
      </div>
    </a>
  );
}

// Rebuild the turns of a saved chat from its messages.
function turnsFrom(conversation: Conversation): Turn[] {
  const turns: Turn[] = [];
  for (const m of conversation.messages) {
    if (m.role === "user") turns.push({ id: m.id, question: m.content });
    else if (turns.length) {
      const p = m.payload as Partial<AskResponse>;
      turns[turns.length - 1].response = {
        conversation_id: conversation.id, kind: (m.kind ?? "answer") as AskResponse["kind"], answer: m.content,
        sources: p.sources ?? [], action: p.action ?? null, prompt_tokens: p.prompt_tokens ?? 0,
        completion_tokens: p.completion_tokens ?? 0, seconds: p.seconds ?? 0,
      };
    }
  }
  return turns;
}

// One chat. Without an id it starts a new one; the first answer gives it an id and the address
// becomes /c/<id> (without reloading), and the sidebar's recent chats refresh.
export function Chat({ conversationId }: { conversationId?: string }) {
  const router = useRouter();
  const { user } = useUser();
  const nextId = useRef(1_000_000);
  const generation = useRef(0);  // bumped by New chat, so a late answer from the old chat is ignored
  const [chatId, setChatId] = useState<string | undefined>(conversationId);
  const [loading, setLoading] = useState(!!conversationId);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [highlight, setHighlight] = useState<{ turn: number; n: number } | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!conversationId) return;
    api.conversation(conversationId)
      .then((c) => setTurns(turnsFrom(c)))
      .catch(() => router.replace("/"))  // deleted, or not this person's chat
      .finally(() => setLoading(false));
  }, [conversationId, router]);

  // New chat while this one is open (its address may already say /c/<id>): start over
  useEffect(() => {
    const reset = () => {
      generation.current += 1;
      setBusy(false);
      setTurns([]);
      setChatId(undefined);
      setQuestion("");
      setHighlight(null);
      setLoading(false);
      if (window.location.pathname !== "/") window.history.replaceState(null, "", "/");
      window.dispatchEvent(new Event(CHATS_CHANGED));  // the sidebar stops highlighting the old chat
    };
    window.addEventListener(NEW_CHAT, reset);
    return () => window.removeEventListener(NEW_CHAT, reset);
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const id = ++nextId.current;
    setTurns((t) => [...t, { id, question: q }]);
    setQuestion("");
    setBusy(true);
    try {
      const asked = generation.current;
      const response = await api.ask(q, chatId);
      if (asked !== generation.current) return;  // the person started a new chat meanwhile
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, response } : turn)));
      if (!chatId) {
        setChatId(response.conversation_id);
        window.history.replaceState(null, "", `/c/${response.conversation_id}`);
      }
      window.dispatchEvent(new Event(CHATS_CHANGED));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        router.replace("/login");
        return;
      }
      const error = e instanceof Error ? e.message : "Something went wrong";
      setTurns((t) => t.map((turn) => (turn.id === id ? { ...turn, error } : turn)));
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      ask(question);
    }
  }

  function cite(turnId: number, n: number) {
    setHighlight({ turn: turnId, n });
    document.getElementById(`src-${turnId}-${n}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <>
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col px-4">
        <div className="flex-1 space-y-8 py-8">
          {loading && <div className="mx-auto h-24 w-full animate-pulse rounded-2xl bg-navy/5" />}
          {!loading && turns.length === 0 && (
            <div className="py-12 text-center">
              <h1 className="text-2xl font-semibold">
                {user ? `Hi ${user.name.split(" ")[0]}, what do you want to know?` : "What do you want to know?"}
              </h1>
              <p className="mt-2 text-sm text-muted">
                Answers come from the handbook and the Slack, issues and wiki pages you can access, with a citation for every claim.
              </p>
              <div className="mx-auto mt-6 grid max-w-2xl gap-2 sm:grid-cols-2">
                {EXAMPLES.map((example) => (
                  <button key={example} onClick={() => ask(example)}
                    className="rounded-xl border border-border bg-surface px-4 py-3 text-left text-sm hover:border-brand/60">
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {turns.map((turn) => (
            <section key={turn.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-navy px-4 py-2.5 text-sm text-surface">
                  {turn.question}
                </div>
              </div>

              <div className="rounded-2xl border border-border bg-surface p-5">
                {!turn.response && !turn.error && (
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
                    Searching your sources…
                  </div>
                )}
                {turn.error && <p className="text-sm text-red-600 dark:text-red-400">{turn.error}</p>}
                {turn.response && (
                  <>
                    {turn.response.kind === "action" && turn.response.action
                      ? <ActionCard action={turn.response.action} />
                      : <AnswerText text={turn.response.answer} onCite={(n) => cite(turn.id, n)} />}
                    {turn.response.sources.length > 0 && (
                      <div className="mt-4 border-t border-border pt-4">
                        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Sources</div>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {turn.response.sources.map((source) => (
                            <SourceCard key={source.number} source={source} turnId={turn.id}
                              highlighted={highlight?.turn === turn.id && highlight.n === source.number} />
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="mt-3 text-[11px] text-muted">
                      {turn.response.seconds.toFixed(1)} s ·{" "}
                      {turn.response.prompt_tokens + turn.response.completion_tokens} tokens
                    </div>
                  </>
                )}
              </div>
            </section>
          ))}
          <div ref={bottom} />
        </div>

        <div className="sticky bottom-0 bg-background pb-4 pt-2">
          <div className="flex items-end gap-2 rounded-2xl border border-border bg-surface p-2 shadow-sm focus-within:border-brand">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder="Ask about policies, processes, engineering…"
              className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
            />
            <button onClick={() => ask(question)} disabled={busy || question.trim().length < 3}
              className="rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-50">
              {busy ? "…" : "Ask"}
            </button>
          </div>
          <p className="mt-2 text-center text-[11px] text-muted">
            Unofficial · answers can be wrong · check the cited source
          </p>
        </div>
      </main>
    </>
  );
}
