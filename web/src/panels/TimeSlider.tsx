/**
 * NISAR date slider (SPEC §10.2): ticks placed in proportion to time, known gaps shaded,
 * play/pause at 1 step/s, arrow keys move one step (on the slider, or anywhere outside a form field).
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { formatDate, isoDay, type Lang } from "../format";
import { useApp } from "../store";

interface Props {
  dates: string[];
  gaps: [string, string][];
}

export default function TimeSlider({ dates, gaps }: Props) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const date = useApp((s) => s.date);
  const setDate = useApp((s) => s.setDate);
  const [playing, setPlaying] = useState(false);

  const idx = Math.max(0, date ? dates.indexOf(date) : dates.length - 1);
  const go = useCallback(
    (i: number) => {
      if (!dates.length) return;
      setDate(dates[Math.min(dates.length - 1, Math.max(0, i))]);
    },
    [dates, setDate],
  );

  // play: one step per second, looping
  useEffect(() => {
    if (!playing || dates.length < 2) return;
    const id = window.setInterval(() => {
      const cur = useApp.getState().date;
      const i = cur ? dates.indexOf(cur) : -1;
      setDate(dates[(i + 1) % dates.length]);
    }, 1000);
    return () => window.clearInterval(id);
  }, [playing, dates, setDate]);

  // arrow keys anywhere (except while typing in a field or using another slider)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      const el = e.target as HTMLElement | null;
      if (el && (el.closest("input, select, textarea, [role=slider], .maplibregl-canvas") || el.isContentEditable)) return;
      e.preventDefault();
      go(idx + (e.key === "ArrowRight" ? 1 : -1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, idx]);

  if (!dates.length) return null;
  const d0 = isoDay(dates[0]);
  const span = Math.max(1, isoDay(dates[dates.length - 1]) - d0);
  const pos = (iso: string) => `${(Math.min(Math.max(isoDay(iso) - d0, 0), span) / span) * 100}%`;
  const current = dates[idx];

  const onSliderKey = (e: React.KeyboardEvent) => {
    const step: Record<string, number> = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 };
    if (e.key in step) go(idx + step[e.key]);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(dates.length - 1);
    else return;
    e.preventDefault();
  };

  return (
    <div className="flex h-[72px] shrink-0 items-center gap-3 border-t border-slate-200 bg-white px-4" data-testid="time-slider">
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        aria-label={playing ? t("slider.pause") : t("slider.play")}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-800 text-white hover:bg-slate-700"
      >
        {playing ? (
          <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden><rect x="3" y="2" width="3.5" height="12" fill="currentColor" /><rect x="9.5" y="2" width="3.5" height="12" fill="currentColor" /></svg>
        ) : (
          <svg viewBox="0 0 16 16" className="h-4 w-4" aria-hidden><path d="M4 2l10 6-10 6z" fill="currentColor" /></svg>
        )}
      </button>
      <div className="w-32 shrink-0 text-center sm:w-40">
        <div className="text-[11px] uppercase tracking-wide text-slate-500">{t("slider.label")}</div>
        <output className="text-sm font-semibold" data-testid="slider-date" aria-live="polite">
          {formatDate(current, lang)}
        </output>
      </div>
      <div className="relative mx-2 h-10 min-w-0 flex-1">
        {/* gaps */}
        {gaps.map(([a, b]) => (
          <div
            key={a}
            className="absolute top-1 h-5 rounded-sm bg-[repeating-linear-gradient(45deg,#e2e8f0,#e2e8f0_4px,#f8fafc_4px,#f8fafc_8px)]"
            style={{ left: pos(a), width: `calc(${pos(b)} - ${pos(a)})` }}
            title={t("slider.gap")}
          >
            <span className="absolute left-1/2 top-6 hidden -translate-x-1/2 whitespace-nowrap text-[10px] text-slate-500 sm:inline">
              {t("slider.gap")}
            </span>
          </div>
        ))}
        {/* track + slider */}
        <div
          role="slider"
          tabIndex={0}
          aria-label={t("slider.label")}
          aria-valuemin={0}
          aria-valuemax={dates.length - 1}
          aria-valuenow={idx}
          aria-valuetext={formatDate(current, lang, "long")}
          onKeyDown={onSliderKey}
          className="absolute inset-x-0 top-3 h-1 rounded bg-slate-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-600 focus-visible:ring-offset-4"
        >
          {dates.map((d, i) => (
            <button
              key={d}
              type="button"
              tabIndex={-1}
              onClick={() => go(i)}
              title={formatDate(d, lang)}
              aria-label={formatDate(d, lang, "long")}
              className={`absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 ${
                i === idx
                  ? "h-5 w-5 border-slate-900 bg-white shadow"
                  : "h-3 w-3 border-slate-500 bg-slate-500 hover:bg-slate-700"
              }`}
              style={{ left: pos(d) }}
            />
          ))}
        </div>
      </div>
      <div className="flex shrink-0 gap-1">
        <button type="button" onClick={() => go(idx - 1)} aria-label={t("slider.prev")} className="rounded px-2 py-1 hover:bg-slate-100" disabled={idx === 0}>
          ‹
        </button>
        <button type="button" onClick={() => go(idx + 1)} aria-label={t("slider.next")} className="rounded px-2 py-1 hover:bg-slate-100" disabled={idx === dates.length - 1}>
          ›
        </button>
      </div>
    </div>
  );
}
