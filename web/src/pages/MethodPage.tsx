/**
 * /method (SPEC §10.1): docs/METHOD.md (Bangla: docs/METHOD.bn.md), imported at build time, then the site's
 * live validation numbers, limitations and data credits.
 */

import { marked } from "marked";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import mdBn from "../../../docs/METHOD.bn.md?raw";
import mdEn from "../../../docs/METHOD.md?raw";
import type { Validation } from "../api/client";
import { useLayers, useStats, useValidation } from "../api/hooks";
import { formatDate, formatNumber, formatPercent, formatYear, type Lang } from "../format";
import { useApp } from "../store";
import { Credits } from "./Credits";
import PageShell from "./PageShell";

function ValidationNumbers({ v, lang, synthetic }: { v: Validation; lang: Lang; synthetic: boolean }) {
  const { t } = useTranslation();
  const n = (x: number | null | undefined, d = 0) => formatNumber(x, lang, { decimals: d });
  const area = v.area_check;
  const s2 = v.sentinel2_check;
  const river = s2?.river_median3;
  const px = s2?.pixel_m ?? 10;
  return (
    <div className="space-y-4">
      <p className="rounded bg-slate-100 p-3" data-testid="validation-status">
        {v.accuracy
          ? t("method.validated", {
              n: n(v.accuracy.n),
              oa: formatPercent(v.accuracy.overall_accuracy, lang),
              kappa: n(v.accuracy.kappa, 2),
            })
          : synthetic
            ? t("method.notValidatedDemo")
            : t("method.notValidated")}
      </p>
      {v.accuracy && (
        <table className="text-sm">
          <caption className="mb-1 text-left font-semibold">{t("method.confusion")}</caption>
          <thead>
            <tr>
              <th />
              <th className="px-3 text-right">{t("method.labelWater")}</th>
              <th className="px-3 text-right">{t("method.labelLand")}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th className="text-left font-normal">{t("method.mappedWater")}</th>
              <td className="px-3 text-right">{n(v.accuracy.confusion.tp)}</td>
              <td className="px-3 text-right">{n(v.accuracy.confusion.fp)}</td>
            </tr>
            <tr>
              <th className="text-left font-normal">{t("method.mappedLand")}</th>
              <td className="px-3 text-right">{n(v.accuracy.confusion.fn)}</td>
              <td className="px-3 text-right">{n(v.accuracy.confusion.tn)}</td>
            </tr>
          </tbody>
        </table>
      )}
      {area?.closest_year && area.closest_year.length > 0 && (
        <div>
          <h3 className="mb-1 font-semibold">{t("method.areaTitle")}</h3>
          <table className="w-full text-sm" data-testid="validation-area">
            <thead>
              <tr className="border-b border-slate-300 text-left">
                <th className="py-1 pr-2">{t("method.published")}</th>
                <th className="py-1 pr-2 text-right">{t("method.ours")}</th>
                <th className="py-1 text-right">{t("method.difference")}</th>
              </tr>
            </thead>
            <tbody>
              {area.closest_year.map((r) => (
                <tr key={r.published_year} className="border-b border-slate-100">
                  <td className="py-1 pr-2">
                    {t("method.km2Year", { v: n(r.published_km2), year: formatYear(r.published_year, lang) })}
                  </td>
                  <td className="py-1 pr-2 text-right">
                    {t("method.km2Year", { v: n(r.landsat_km2), year: formatYear(r.landsat_year, lang) })}
                  </td>
                  <td className="py-1 text-right">{n(r.diff_pct, 1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-1 text-sm text-slate-600">
            {area.within_15pct ? t("method.areaOk") : t("method.areaOff")}
          </p>
        </div>
      )}
      {s2?.status === "ok" && river && (
        <div>
          <h3 className="mb-1 font-semibold">{t("method.s2Title")}</h3>
          <p className="text-sm" data-testid="validation-s2">
            {t("method.s2Text", {
              nisar: formatDate(s2.nisar_date, lang),
              s2: formatDate(s2.sentinel2_date, lang),
              iou: n(river.river_iou, 2),
              median: n((river.outline_dist_px_median ?? 0) * px),
              within: formatPercent(river.outline_within_2px_frac, lang),
            })}
          </p>
          {(river.nisar_wetter_frac ?? 0) > 0.75 && <p className="mt-1 text-sm text-slate-600">{t("method.s2Wetter")}</p>}
        </div>
      )}
    </div>
  );
}

export default function MethodPage() {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const site = useApp((s) => s.site);
  const validation = useValidation(site);
  const layers = useLayers(site);
  const stats = useStats(site);
  const html = useMemo(() => marked.parse(lang === "bn" ? mdBn : mdEn, { async: false }) as string, [lang]);
  const manifest = layers.data?.site === site ? layers.data : undefined;
  const siteName = manifest ? manifest.name[lang] ?? manifest.name.en : site ?? "";

  return (
    <PageShell title={t("nav.method")}>
      {/* our own Markdown, compiled into the bundle (no user content) */}
      <article className="md" dangerouslySetInnerHTML={{ __html: html }} />

      <section className="mt-8" aria-labelledby="validation-h" data-testid="validation-section">
        <h2 id="validation-h" className="mb-2 text-xl font-semibold">
          {t("method.validationTitle", { site: siteName })}
        </h2>
        {validation.isPending && <div className="h-24 animate-pulse rounded bg-slate-100" />}
        {validation.isError && <p role="alert">{t("method.validationError")}</p>}
        {validation.data && <ValidationNumbers v={validation.data} lang={lang} synthetic={!!manifest?.synthetic} />}
      </section>

      <section className="mt-8" aria-labelledby="limits-h" data-testid="limitations">
        <h2 id="limits-h" className="mb-2 text-xl font-semibold">
          {t("limits.title")}
        </h2>
        <ul className="list-disc space-y-1.5 pl-5">
          {manifest?.synthetic && <li className="font-semibold text-red-700">{t("limits.synthetic")}</li>}
          <li>{t("limits.estimate")}</li>
          <li>{t("limits.provisional")}</li>
          <li>{t("limits.gap")}</li>
          <li>{t("limits.tide")}</li>
          <li>{t("limits.rate")}</li>
          {manifest && !manifest.motion_usable && (
            <li>{t("limits.motion", { pct: formatNumber(stats.data?.coherent_land_pct ?? null, lang, { decimals: 1 }) })}</li>
          )}
          <li>{t("limits.population")}</li>
          <li>{t("limits.bangla")}</li>
        </ul>
      </section>

      <section className="mt-8" aria-labelledby="credits-h">
        <h2 id="credits-h" className="mb-2 text-xl font-semibold">
          {t("credits.title")}
        </h2>
        <Credits />
      </section>
    </PageShell>
  );
}
