import { useEffect, useRef, useState } from "react";

export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "posegridgen.theme";
const DARK_MODE_QUERY = "(prefers-color-scheme: dark)";

function isTheme(value: string | null | undefined): value is Theme {
  return value === "light" || value === "dark";
}

function savedTheme(): Theme | undefined {
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

function systemTheme(): Theme {
  return typeof window.matchMedia === "function" && window.matchMedia(DARK_MODE_QUERY).matches
    ? "dark"
    : "light";
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

export function initializeTheme(): Theme {
  const theme = savedTheme() ?? systemTheme();
  applyTheme(theme);
  return theme;
}

function currentTheme(): Theme {
  const stored = savedTheme();
  if (stored) {
    applyTheme(stored);
    return stored;
  }

  const rootTheme = document.documentElement.dataset.theme;
  if (isTheme(rootTheme)) return rootTheme;
  return initializeTheme();
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(currentTheme);
  const hasManualOverride = useRef(savedTheme() !== undefined);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(DARK_MODE_QUERY);
    const updateFromSystem = (event: MediaQueryListEvent) => {
      if (hasManualOverride.current) return;
      const nextTheme = event.matches ? "dark" : "light";
      applyTheme(nextTheme);
      setTheme(nextTheme);
    };

    media.addEventListener("change", updateFromSystem);
    return () => media.removeEventListener("change", updateFromSystem);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    hasManualOverride.current = true;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      // The in-memory choice still applies when storage is unavailable.
    }
    applyTheme(nextTheme);
    setTheme(nextTheme);
  };

  return { theme, toggleTheme };
}
