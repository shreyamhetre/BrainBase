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
    <span className="flex flex-wrap justify-end gap-1">
      {roles.map((role) => (
        <span key={role} className="rounded-full bg-brand/10 px-2 py-0.5 text-xs font-medium text-brand-strong">
          {role}
        </span>
      ))}
    </span>
  );
}

// The logo is the way back to chat. Admins get an Admin button; everyone gets log out
// (or sign in when there is no session yet).
export function Header({ user, active }: { user: User | null; active?: "admin" }) {
  const router = useRouter();

  async function logout() {
    await api.logout();
    router.replace("/login");
  }

  const button = "rounded-md border border-border px-3 py-1.5 text-sm text-muted hover:text-foreground";

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-surface/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
        <Link href="/" aria-label="GitMore chat" className="flex shrink-0 items-center">
          <Image src="/small-logo.png" alt="GitMore" width={40} height={40} priority />
        </Link>
        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          {user && (
            <div className="hidden min-w-0 text-right sm:block">
              <div className="truncate text-sm font-medium">{user.name}</div>
              {/* Admins hold every role, so listing them adds nothing. */}
              {!user.is_admin && <RoleChips roles={user.roles} />}
            </div>
          )}
          {user?.is_admin && (
            <Link href="/admin"
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                active === "admin" ? "bg-brand text-white" : "bg-brand/10 text-brand-strong hover:bg-brand/20"}`}>
              Admin
            </Link>
          )}
          {user ? (
            <button onClick={logout} className={button}>Log out</button>
          ) : (
            <Link href="/login" className={button}>Sign in</Link>
          )}
        </div>
      </div>
    </header>
  );
}
