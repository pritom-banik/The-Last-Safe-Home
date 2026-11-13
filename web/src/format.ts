/** Number and date formatting with Intl (SPEC §10.8): en-GB for English, bn-BD for Bangla. */

export type Lang = "en" | "bn";

export const LANGS: Lang[] = ["en", "bn"];

export function locale(lang: Lang): string {
  return lang === "bn" ? "bn-BD" : "en-GB";
}

export function isLang(x: unknown): x is Lang {
  return x === "en" || x === "bn";
}

export function formatNumber(
  value: number | null | undefined,
  lang: Lang,
  opts: { decimals?: number; signed?: boolean } = {},
): string {
  if (value == null || !Number.isFinite(value)) return "–";
  const d = opts.decimals ?? 0;
  return new Intl.NumberFormat(locale(lang), {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
    signDisplay: opts.signed ? "exceptZero" : "auto",
  }).format(value);
}

/** 0.42 → "42%" (৪২% in Bangla). */
export function formatPercent(fraction: number | null | undefined, lang: Lang): string {
  if (fraction == null || !Number.isFinite(fraction)) return "–";
  return new Intl.NumberFormat(locale(lang), { style: "percent", maximumFractionDigits: 0 }).format(fraction);
}

/** ISO "2026-09-09" → "9 Sept 2026" / "৯ সেপ, ২০২৬". Parsed as a calendar date (no timezone shift). */
export function formatDate(iso: string | null | undefined, lang: Lang, style: "short" | "long" = "short"): string {
  if (!iso) return "–";
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return new Intl.DateTimeFormat(locale(lang), {
    day: "numeric",
    month: style === "long" ? "long" : "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(d);
}

/** A year as a plain number in the language's digits, without grouping (1988, not 1,988). */
export function formatYear(year: number, lang: Lang): string {
  return new Intl.NumberFormat(locale(lang), { useGrouping: false }).format(year);
}

/** Days since epoch for an ISO date, used to place slider ticks in proportion to time. */
export function isoDay(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d) / 86_400_000;
}
