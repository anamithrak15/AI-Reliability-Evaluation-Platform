import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "theme";

function systemTheme(): Theme {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function stored(): Theme | null {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null; // storage can be blocked; fall back to the system setting
  }
}

/** Light/dark choice: an explicit saved choice wins, otherwise the operating system's setting. */
export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? systemTheme());

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      try {
        window.localStorage.setItem(KEY, next);
      } catch {
        // not persisted; the choice still applies for this visit
      }
      return next;
    });
  }, []);

  return { theme, toggle };
}
