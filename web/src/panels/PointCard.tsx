import { useState } from "react";
import { Trans, useTranslation } from "react-i18next";
import { ApiError, type PointResult } from "../api/client";
import { usePoint } from "../api/hooks";
import { formatDate, formatNumber, formatPercent, type Lang } from "../format";
import { classColour, classTextColour, scoreClass } from "../score";
import { reportPath } from "../report/reportUrl";
import { Link } from "../router";
import { useApp } from "../store";
import { DemoChip, Disclaimer, Row } from "./common";

/** "8–13", "8–50+", "12" — years rounded to whole numbers; anything beyond 50 shown as "50+". */
export function yearsRange(low: number | null, high: number | null, lang: Lang): string {
  const fmt = (v: number | null) => (v == null || v > 50 ? `${formatNumber(50, lang)}+` : formatNumber(Math.round(v), lang));
  const a = fmt(low);
  const b = fmt(high);
  return a === b ? a : `${a}–${b}`;
}

function Outlook({ p, lang }: { p: PointResult; lang: Lang }) {
  const { t } = useTranslation();
  let body: React.ReactNode;
  if (p.in_river) body = t("point.inRiver");
  else if (p.retreat_rate_m_yr == null || p.retreat_rate_m_yr <= 0) body = t("point.growing");
  else if (!p.years_until_river || p.years_until_river.over_50) body = t("point.over50");
  else {
    const y = p.years_until_river;
    body = (
      <Trans i18nKey="point.arrive" values={{ range: yearsRange(y.low ?? y.central, y.high, lang) }} components={{ b: <strong /> }} />
    );
  }
  return (
    <p className="text-base" data-testid="point-outlook">
      {body}
    </p>
  );
}

function Calculation({ p, lang }: { p: PointResult; lang: Lang }) {
  const { t } = useTranslation();
  if (!p.components) return null;
  const n = (v: number) => formatNumber(v, lang, { decimals: 2 });
  const rows: [string, number, number][] = [
    [t("point.hE"), p.components.H_E, p.weights.erosion],
    [t("point.hF"), p.components.H_F, p.weights.flood],
    [t("point.hG"), p.components.H_G, p.weights.motion],
  ];
  return (
    <details className="rounded border border-slate-200 p-2 text-sm">
      <summary className="cursor-pointer font-medium">{t("point.how")}</summary>
      <p className="mt-2 font-mono text-xs">{t("point.formula")}</p>
      <table className="mt-2 w-full text-xs">
        <tbody>
          {rows.map(([label, h, w]) => (
            <tr key={label} className="border-t border-slate-100">
              <td className="py-1 pr-2">{label}</td>
              <td className="py-1 text-right font-mono">{n(h)}</td>
              <td className="py-1 pl-2 text-right font-mono text-slate-500">
                {t("point.weight")} {n(w)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Score, outlook and the numbers for one point; shared by the card and the printable report. */
export function PointSummary({ p, lang }: { p: PointResult; lang: Lang }) {
  const { t } = useTranslation();
  const cls = p.class ?? scoreClass(p.score);
  const m = (v: number | null, d = 0) => formatNumber(v, lang, { decimals: d });

  const motion =
    p.motion_status === "not_usable"
      ? t("point.motionNotUsable")
      : p.motion_status === "masked" || p.motion_mm == null
        ? t("point.motionMasked")
        : t("point.units.mm", { v: formatNumber(p.motion_mm, lang, { decimals: 1, signed: true }) });

  return (
    <>
      {!p.in_river && p.score != null && cls && (
        <div className="flex items-center gap-3">
          <div>
            <div className="text-xs text-slate-500">{t("point.score")}</div>
            <div className="flex items-baseline gap-1">
              <span className="text-5xl font-bold leading-none" data-testid="point-score">
                {m(p.score)}
              </span>
              <span className="text-xs text-slate-500">{t("point.outOf")}</span>
            </div>
          </div>
          <div className="flex-1">
            <span
              className="inline-block rounded px-2 py-0.5 text-sm font-semibold"
              style={{ background: classColour(cls), color: classTextColour(cls) }}
              data-testid="point-class"
            >
              {t(`class.${cls}`)}
            </span>
            <p className="mt-1 text-sm text-slate-700">{t(`class.advice.${cls}`)}</p>
          </div>
        </div>
      )}
      <Outlook p={p} lang={lang} />
      {!p.in_river && (
        <dl className="divide-y divide-slate-100 text-sm">
          <Row label={t("point.distance")} value={t("point.units.m", { v: m(p.distance_to_bank_m) })} />
          <Row
            label={t("point.rate")}
            value={t("point.units.mYr", { v: m(p.retreat_rate_m_yr, 1), s: m(p.retreat_sigma_m_yr, 1) })}
          />
          <Row label={t("point.flood")} value={formatPercent(p.flood_frequency, lang)} />
          <Row label={t("point.motion")} value={motion} />
          <Row label={t("point.lastPass")} value={formatDate(p.data.last_pass, lang)} />
        </dl>
      )}
      {p.data.grid_m != null && (
        <p className="text-xs text-slate-600" data-testid="point-grid-note">
          {t("point.gridNote", { m: formatNumber(p.data.grid_m, lang) })}
        </p>
      )}
    </>
  );
}

export default function PointCard() {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const site = useApp((s) => s.site);
  const point = useApp((s) => s.point);
  const q = usePoint(site, point);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the address bar still has the link */
    }
  };

  if (q.isPending) {
    return (
      <div className="space-y-3" aria-busy="true" data-testid="point-loading">
        <div className="h-16 animate-pulse rounded bg-slate-100" />
        <div className="h-6 animate-pulse rounded bg-slate-100" />
        <div className="h-32 animate-pulse rounded bg-slate-100" />
      </div>
    );
  }
  if (q.isError) {
    const outside = q.error instanceof ApiError && q.error.code === "outside_aoi";
    return (
      <p role="alert" className="rounded bg-slate-100 p-3 text-sm" data-testid="point-error">
        {outside ? t("point.errorOutside") : t("point.errorGeneric")}
      </p>
    );
  }
  const p = q.data;

  return (
    <div className="space-y-3" data-testid="point-card">
      {p.data.synthetic && <DemoChip />}
      <PointSummary p={p} lang={lang} />
      {!p.in_river && <Calculation p={p} lang={lang} />}
      <Disclaimer />
      <div className="flex flex-wrap gap-2">
        {site && point && (
          <Link
            to={reportPath({ kind: "point", site, lon: point[0], lat: point[1], lang })}
            target="_blank"
            rel="noopener"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            data-testid="point-report"
          >
            {t("report.print")}
          </Link>
        )}
        <button type="button" onClick={copy} className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50">
          {copied ? t("point.copied") : t("point.copyLink")}
        </button>
      </div>
    </div>
  );
}
