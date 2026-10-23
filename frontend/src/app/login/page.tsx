"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") await api.login(email, password);
      else await api.signup(name, email, password);
      router.replace("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-brand focus:ring-2 focus:ring-brand/20";

  return (
    <main className="flex flex-1 items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <Image src="/gitmore-logo.png" alt="GitMore: one brain across your company's tools" width={236} height={80} priority />
        </div>

        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h1 className="text-lg font-semibold">{mode === "login" ? "Log in" : "Create an account"}</h1>

          {mode === "signup" && (
            <label className="block space-y-1">
              <span className="text-sm text-muted">Name</span>
              <input className={input} value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
          )}
          <label className="block space-y-1">
            <span className="text-sm text-muted">Email</span>
            <input className={input} type="email" autoComplete="email" value={email}
              onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block space-y-1">
            <span className="text-sm text-muted">Password</span>
            <input className={input} type="password" minLength={mode === "signup" ? 8 : undefined}
              autoComplete={mode === "login" ? "current-password" : "new-password"} value={password}
              onChange={(e) => setPassword(e.target.value)} required />
          </label>

          {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-400">{error}</p>}

          <button type="submit" disabled={busy}
            className="w-full rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-strong disabled:opacity-60">
            {busy ? "Please wait…" : mode === "login" ? "Log in" : "Sign up"}
          </button>

          <p className="text-center text-sm text-muted">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <button type="button" className="font-medium text-brand-strong hover:underline"
              onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}>
              {mode === "login" ? "Create an account" : "Log in"}
            </button>
          </p>
          {mode === "signup" && (
            <p className="text-xs text-muted">New accounts can read the handbook. An admin assigns roles for more.</p>
          )}
        </form>

        <p className="mt-6 text-center text-xs text-muted">
          Unofficial learning project. Not affiliated with or endorsed by GitLab.
        </p>
      </div>
    </main>
  );
}
