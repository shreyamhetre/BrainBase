"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { Icon } from "@/components/icons";
import { api, CHATS_CHANGED, type ConversationSummary } from "@/lib/api";
import { useUser } from "@/lib/user-context";

// The person's own chats, newest first. Refreshes when a message is sent anywhere in the app.
export function RecentChats({ onNavigate }: { onNavigate: () => void }) {
  const { user } = useUser();
  const path = usePathname();
  const router = useRouter();
  const [chats, setChats] = useState<ConversationSummary[] | null>(null);
  const [removing, setRemoving] = useState<ConversationSummary | null>(null);

  useEffect(() => {
    if (!user) return;
    const load = () => api.conversations().then(setChats).catch(() => setChats([]));
    load();
    window.addEventListener(CHATS_CHANGED, load);
    return () => window.removeEventListener(CHATS_CHANGED, load);
  }, [user]);

  async function remove(chat: ConversationSummary) {
    setRemoving(null);
    await api.deleteConversation(chat.id).catch(() => {});
    setChats((all) => (all ?? []).filter((c) => c.id !== chat.id));
    if (path === `/c/${chat.id}` || window.location.pathname === `/c/${chat.id}`) router.push("/");
  }

  // The chat page changes the address itself after its first answer, so read it from the window too
  const current = typeof window !== "undefined" ? window.location.pathname : path;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">Recent chats</div>
      {chats === null && <div className="mx-3 h-16 animate-pulse rounded-lg bg-navy/5" />}
      {chats?.length === 0 && <p className="px-3 text-xs text-muted">Your conversations will be listed here.</p>}
      <ul className="space-y-0.5">
        {chats?.map((chat) => {
          const active = current === `/c/${chat.id}`;
          return (
            <li key={chat.id} className="group relative">
              <Link href={`/c/${chat.id}`} onClick={onNavigate} title={chat.title} aria-current={active ? "page" : undefined}
                className={`block truncate rounded-lg py-1.5 pl-3 pr-8 text-sm transition ${
                  active ? "bg-navy/10 font-medium text-foreground" : "text-muted hover:bg-navy/5 hover:text-foreground"}`}>
                {chat.title}
              </Link>
              <button onClick={() => setRemoving(chat)} aria-label={`Delete chat: ${chat.title}`}
                className="absolute right-1 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted opacity-0 transition hover:bg-red-500/10 hover:text-red-600 focus:opacity-100 group-hover:opacity-100">
                <Icon name="close" className="h-3.5 w-3.5" />
              </button>
            </li>
          );
        })}
      </ul>

      {removing && (
        <ConfirmDialog title="Delete this chat?" yesLabel="Delete" noLabel="Cancel" tone="danger"
          onYes={() => remove(removing)} onNo={() => setRemoving(null)}>
          &ldquo;{removing.title}&rdquo; and its messages are deleted. Actions already posted in GitLab stay there.
        </ConfirmDialog>
      )}
    </div>
  );
}
