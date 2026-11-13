/** Build-time settings. VITE_API_URL is set from API_URL in .env (SPEC §4.1). */

export function apiBase(raw: string | undefined): string {
  const base = (raw && raw.trim()) || "http://localhost:8000";
  const trimmed = base.replace(/\/+$/, "");
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

export const API_BASE = apiBase(import.meta.env.VITE_API_URL);

/** Default view before a site is loaded: Manpura Island (SPEC §4.2). */
export const DEFAULT_VIEW = { center: [90.97, 22.28] as [number, number], zoom: 11 };

/** Source code (MIT). */
export const REPO_URL = "https://github.com/AriyaArKa/nasa";

/** The team, shown on /about (NASA Space Apps Challenge 2026). */
export const TEAM_NAME = "Nova Logits";
export const LOCAL_EVENT = "Khulna";
export const TEAM: string[] = ["Pritom Banik", "Arka Braja Prasad Nath", "Megha Tania", "Enam E Elahi"];

/** Static edition (no API): base URL of the files from `python -m api.static_export`, e.g. "/static". */
export function staticBase(raw: string | undefined): string | null {
  const v = raw?.trim();
  return v ? v.replace(/\/+$/, "") : null;
}

export const STATIC_URL = staticBase(import.meta.env.VITE_STATIC_URL);
