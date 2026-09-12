// Tema dark/light selectable (persistido en localStorage, con fallback al sistema).
const KEY = "aibsl-theme";

export function applyTheme(): void {
  const saved = (() => {
    try { return localStorage.getItem(KEY); } catch { return null; }
  })();
  document.documentElement.setAttribute("data-theme", saved || "");
}

export function toggleTheme(): void {
  const cur = document.documentElement.getAttribute("data-theme");
  const next = cur === "dark" ? "" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem(KEY, next); } catch { /* private mode */ }
}

export function isDark(): boolean {
  const t = document.documentElement.getAttribute("data-theme");
  if (t === "dark") return true;
  if (t === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}