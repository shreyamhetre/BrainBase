"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, type User } from "@/lib/api";

export function RoleChips({ roles }: { roles: string[] }) {
  if (roles.length === 0) {
    return <span className="text-xs text-muted">handbook only</span>;
  }
  return (
    <span className="flex flex-wrap gap-1">
      {roles.map((role) => (
        <span key={role} className="rounded-full bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand-strong">
          {role}
        </span>
      ))}
    </span>
  );
}

export function Header({ user, active }: { user: User | null; active: "chat" | "admin" }) {
  const router = useRouter();

  async function logout() {
    await api.logout();
    router.replace("/login");
  }

  const tab = (name: "chat" | "admin") =>
    `rounded-md px-3 py-1.5 text-sm font-medium ${
      active === name ? "bg-navy/10 text-foreground" : "text-muted hover:text-foreground"
    }`;

  return (
    <header className="sticky top-0 z-10 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <Link href="/" className="flex shrink-0 items-center">
          <Image src="/gitmore-logo.png" alt="GitMore" width={118} height={40} priority />
        </Link>
        <nav className="flex items-center gap-1">
          <Link href="/" className={tab("chat")}>Chat</Link>
          {user?.is_admin && <Link href="/admin" className={tab("admin")}>Admin</Link>}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {user && (
            <div className="hidden text-right sm:block">
              <div className="text-sm font-medium">{user.name}</div>
              <RoleChips roles={user.roles} />
            </div>
          )}
          <button
            onClick={logout}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-foreground"
          >
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}
