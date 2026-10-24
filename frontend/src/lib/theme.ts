import { useSyncExternalStore } from "react";

// Light / dark / system theme, remembered in this browser. "system" removes the
// data-theme attribute so globals.css follows prefers-color-scheme.

export type Theme = "system" | "light" | "dark";

import { THEME_KEY as KEY } from "./theme-script";

export function readTheme(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme: Theme) {
  try {
    if (theme === "system") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, theme);
  } catch {
    // storage blocked: the choice still applies until reload
  }
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  listeners.forEach((notify) => notify());
}

const listeners = new Set<() => void>();
const subscribe = (notify: () => void) => {
  listeners.add(notify);
  return () => listeners.delete(notify);
};

// The current choice; the server always renders "system" and the browser corrects it after hydration.
export const useTheme = () => useSyncExternalStore(subscribe, readTheme, () => "system" as Theme);
