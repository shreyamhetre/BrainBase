"use client";

import { PageHeader } from "@/components/app-shell";
import { Icon, type IconName } from "@/components/icons";
import { applyTheme, useTheme, type Theme } from "@/lib/theme";

const THEMES: { id: Theme; label: string; icon: IconName }[] = [
  { id: "system", label: "System", icon: "monitor" },
  { id: "light", label: "Light", icon: "sun" },
  { id: "dark", label: "Dark", icon: "moon" },
];

export default function SettingsPage() {
  const theme = useTheme();

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 lg:px-8">
      <PageHeader title="Settings" description="Preferences for this browser." />

      <section className="grid gap-4 border-t border-border py-8 md:grid-cols-[16rem_1fr] md:gap-8">
        <div>
          <h2 className="text-sm font-semibold">Appearance</h2>
          <p className="mt-1 text-sm text-muted">System follows your device&apos;s light or dark mode.</p>
        </div>
        <div role="radiogroup" aria-label="Theme" className="grid gap-3 sm:grid-cols-3">
          {THEMES.map((t) => (
            <button key={t.id} role="radio" aria-checked={theme === t.id} onClick={() => applyTheme(t.id)}
              className={`flex items-center gap-3 rounded-xl border bg-surface p-4 text-left text-sm font-medium shadow-sm transition ${
                theme === t.id ? "border-brand ring-2 ring-brand/20" : "border-border hover:border-brand/50"}`}>
              <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${theme === t.id ? "bg-brand text-white" : "bg-navy/5 text-muted"}`}>
                <Icon name={t.icon} className="h-[18px] w-[18px]" />
              </span>
              {t.label}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
