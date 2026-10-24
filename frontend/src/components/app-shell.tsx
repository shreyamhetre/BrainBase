"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Avatar } from "@/components/avatar";
import { Icon, type IconName } from "@/components/icons";
import { api } from "@/lib/api";
import { useUser } from "@/lib/user-context";

function NavLink({ href, icon, label, active, badge, onNavigate }: {
  href: string; icon: IconName; label: string; active: boolean; badge?: number; onNavigate: () => void;
}) {
  return (
    <Link href={href} onClick={onNavigate} aria-current={active ? "page" : undefined}
      className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
        active ? "bg-brand/10 text-brand-strong" : "text-muted hover:bg-navy/5 hover:text-foreground"}`}>
      <Icon name={icon} className="h-[18px] w-[18px] shrink-0" />
      <span className="flex-1 truncate">{label}</span>
      {!!badge && (
        <span className="rounded-full bg-brand px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white">{badge}</span>
      )}
    </Link>
  );
}

function ProfileMenu({ onNavigate }: { onNavigate: () => void }) {
  const router = useRouter();
  const { user } = useUser();
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

  async function logout() {
    await api.logout();
    router.replace("/login");
  }

  if (!user) return <div className="h-12 animate-pulse rounded-lg bg-navy/5" />;

  const item = "flex w-full items-center gap-3 px-3 py-2 text-left text-sm text-foreground hover:bg-navy/5";
  const go = () => { setOpen(false); onNavigate(); };

  return (
    <div ref={box} className="relative">
      {open && (
        <div role="menu" className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-xl border border-border bg-surface py-1 shadow-xl">
          <div className="flex items-center gap-3 border-b border-border px-3 py-3">
            <Avatar name={user.name} admin={user.is_admin} />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{user.name}</div>
              <div className="truncate text-xs text-muted">{user.email}</div>
              <div className="mt-0.5 text-[11px] text-muted">
                {user.is_admin ? "Admin · all roles" : user.roles.length ? user.roles.join(", ") : "Handbook only"}
              </div>
            </div>
          </div>
          <Link href="/profile" role="menuitem" onClick={go} className={item}><Icon name="user" className="h-4 w-4 text-muted" />Profile</Link>
          {!user.is_admin && (
            <Link href="/profile#access" role="menuitem" onClick={go} className={item}><Icon name="key" className="h-4 w-4 text-muted" />Request access</Link>
          )}
          <Link href="/settings" role="menuitem" onClick={go} className={item}><Icon name="settings" className="h-4 w-4 text-muted" />Settings</Link>
          <div className="my-1 border-t border-border" />
          <button role="menuitem" onClick={logout} className={item}><Icon name="logout" className="h-4 w-4 text-muted" />Log out</button>
        </div>
      )}
      <button onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}
        className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-navy/5">
        <Avatar name={user.name} admin={user.is_admin} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium">{user.name}</span>
          <span className="block truncate text-xs text-muted">{user.email}</span>
        </span>
        <Icon name="chevron" className={`h-4 w-4 shrink-0 text-muted transition ${open ? "-rotate-90" : ""}`} />
      </button>
    </div>
  );
}

function Sidebar({ onNavigate }: { onNavigate: () => void }) {
  const path = usePathname();
  const { user } = useUser();
  const [pending, setPending] = useState(0);

  useEffect(() => {
    if (user?.is_admin) api.overview().then((o) => setPending(o.pending_requests)).catch(() => {});
  }, [user, path]);

  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <Link href="/" onClick={onNavigate} className="flex items-center gap-2 px-2 pt-1">
        <Image src="/small-logo.png" alt="" width={32} height={32} priority />
        <span className="text-lg font-bold tracking-tight"><span className="text-navy">Git</span><span className="text-brand">More</span></span>
      </Link>

      <Link href="/" onClick={onNavigate}
        className="flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium shadow-sm hover:border-brand/60">
        <Icon name="plus" className="h-4 w-4" /> New chat
      </Link>

      <nav className="space-y-0.5" aria-label="Main">
        <NavLink href="/" icon="chat" label="Chat" active={path === "/"} onNavigate={onNavigate} />
        <NavLink href="/connectors" icon="plug" label="Connectors" active={path === "/connectors"} onNavigate={onNavigate} />
        <NavLink href="/mcp" icon="tool" label="MCP tools" active={path === "/mcp"} onNavigate={onNavigate} />
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted">Recent chats</div>
        <p className="px-3 text-xs text-muted">Your conversations will be listed here.</p>
      </div>

      <div className="space-y-1 border-t border-border pt-3">
        {user?.is_admin && (
          <NavLink href="/admin" icon="shield" label="Admin console" active={path.startsWith("/admin")}
            badge={pending} onNavigate={onNavigate} />
        )}
        <ProfileMenu onNavigate={onNavigate} />
      </div>
    </div>
  );
}

// Left sidebar on large screens; on phones and tablets a top bar with a menu button opens it as a drawer.
export function AppShell({ children }: { children: ReactNode }) {
  const [drawer, setDrawer] = useState(false);

  // Links inside the drawer close it through onNavigate.
  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawer]);

  return (
    <div className="flex min-h-full flex-1">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-border bg-surface lg:block">
        <Sidebar onNavigate={() => {}} />
      </aside>

      {drawer && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 max-w-[85%] border-r border-border bg-surface shadow-xl">
            <button onClick={() => setDrawer(false)} aria-label="Close menu"
              className="absolute right-2 top-3 rounded-md p-1.5 text-muted hover:bg-navy/5 hover:text-foreground">
              <Icon name="close" />
            </button>
            <Sidebar onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-surface/90 px-4 backdrop-blur lg:hidden">
          <button onClick={() => setDrawer(true)} aria-label="Open menu" className="-ml-1.5 rounded-md p-1.5 hover:bg-navy/5">
            <Icon name="menu" />
          </button>
          <Link href="/" className="flex items-center gap-2">
            <Image src="/small-logo.png" alt="" width={28} height={28} />
            <span className="font-bold tracking-tight"><span className="text-navy">Git</span><span className="text-brand">More</span></span>
          </Link>
        </header>
        {children}
      </div>
    </div>
  );
}

// Page title block shared by the inner pages.
export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-muted">{description}</p>}
      </div>
      {actions}
    </div>
  );
}
