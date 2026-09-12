// Formatos pequeños reutilizables.
export const fmtPct = (v: number, digits = 1): string =>
  `${(v * 100).toFixed(digits)}%`;

export const fmtTick = (v: number | null | undefined): string =>
  v === null || v === undefined ? "—" : `t${v}`;

export const fmtTime = (iso: string | null | undefined): string => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("es", { hour12: false });
};

export const clamp01 = (v: number): number => Math.max(0, Math.min(1, v));