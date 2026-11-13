import { useTranslation } from "react-i18next";
import { ApiError, type PolygonStats } from "../api/client";
import { usePolygonStats, useScenes } from "../api/hooks";
import { formatDate, formatNumber, type Lang } from "../format";
import { reportPath } from "../report/reportUrl";
import { Link } from "../router";
import { useApp } from "../store";
import { DemoChip, Disclaimer, PeopleBar, Row } from "./common";

function SceneList({ polygon, lang }: { polygon: GeoJSON.Polygon; lang: Lang }) {
  const { t } = useTranslation();
  const q = useScenes(polygon);
  let body: React.ReactNode;
  if (q.isPending) body = <p className="text-sm text-slate-500">{t("scenes.loading")}</p>;
  else if (q.isError)
    body = (
      <p className="text-sm text-slate-600">
        {q.error instanceof ApiError && q.error.code === "static_unavailable" ? t("scenes.staticUnavailable") : t("scenes.error")}
      </p>
    );
  else if (!q.data.length) body = <p className="text-sm text-slate-600">{t("scenes.none")}</p>;
  else
    body = (
      <ul className="max-h-64 divide-y divide-slate-100 overflow-y-auto text-sm" data-testid="scene-list">
        {q.data.map((s) => (
          <li key={s.granule} className="flex items-center justify-between gap-2 py-1.5">
            <span>
              {formatDate(s.datetime.slice(0, 10), lang)} · {s.product} · {t(`scenes.dir.${s.direction === "ASCENDING" ? "asc" : s.direction === "DESCENDING" ? "desc" : "other"}`)}{" "}
              · {t("scenes.track", { v: s.track })}
            </span>
            <a href={s.url_asf} target="_blank" rel="noreferrer" className="text-sky-700 underline">
              {t("scenes.open")}
            </a>
          </li>
        ))}
      </ul>
    );
  return (
    <section>
      <h3 className="mb-1 text-sm font-semibold">
        {t("scenes.title")}
        {q.data && q.data.length > 0 && <span className="ml-1 font-normal text-slate-500">({formatNumber(q.data.length, lang)})</span>}
      </h3>
      {body}
    </section>
  );
}

/** Area numbers and people by class; shared by the panel and the printable report. */
export function PolygonSummary({ p, lang }: { p: PolygonStats; lang: Lang }) {
  const { t } = useTranslation();
  const n = (v: number | null | undefined, d = 0) => formatNumber(v, lang, { decimals: d });
  return (
    <>
      <dl className="divide-y divide-slate-100 text-sm" data-testid="polygon-stats">
        <Row label={t("polygon.area")} value={t("polygon.km2", { v: n(p.area_km2, 2) })} />
        <Row label={t("polygon.landArea")} value={t("polygon.km2", { v: n(p.land_area_km2, 2) })} />
        <Row label={t("polygon.landLost")} value={t("polygon.km2yr", { v: n(p.area_lost_km2_per_yr, 3) })} />
        <Row label={t("polygon.meanScore")} value={n(p.mean_score)} />
        <Row label={t("polygon.maxRetreat")} value={t("polygon.mYr", { v: n(p.max_retreat_m_yr) })} />
        <Row label={t("polygon.buildingsTotal")} value={<span data-testid="buildings-total">{n(p.buildings_total)}</span>} />
        <Row label={t("polygon.buildings100")} value={n(p.buildings_within_100m)} />
        <Row label={t("polygon.buildings500")} value={n(p.buildings_within_500m)} />
        <Row label={t("polygon.transects")} value={n(p.transects)} />
      </dl>
      {p.people_by_class && (
        <section>
          <h3 className="mb-1 text-sm font-semibold">{t("polygon.people")}</h3>
          <PeopleBar counts={p.people_by_class} lang={lang} />
        </section>
      )}
    </>
  );
}

function download(polygon: GeoJSON.Polygon) {
  const fc = { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: polygon }] };
  const url = URL.createObjectURL(new Blob([JSON.stringify(fc)], { type: "application/geo+json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "area.geojson";
  a.click();
  URL.revokeObjectURL(url);
}

export default function PolygonPanel() {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const site = useApp((s) => s.site);
  const polygon = useApp((s) => s.polygon);
  const setPolygon = useApp((s) => s.setPolygon);
  const q = usePolygonStats(site, polygon);
  if (!polygon) return null;

  let stats: React.ReactNode;
  if (q.isPending) stats = <div className="h-48 animate-pulse rounded bg-slate-100" aria-busy="true" />;
  else if (q.isError) {
    const code = q.error instanceof ApiError ? q.error.code : "";
    stats = (
      <p role="alert" className="rounded bg-slate-100 p-3 text-sm">
        {code === "too_large"
          ? t("polygon.tooLarge")
          : code === "invalid_geometry"
            ? t("polygon.invalid")
            : code === "static_unavailable"
              ? t("polygon.staticUnavailable")
              : t("polygon.errorGeneric")}
      </p>
    );
  } else if (!q.data.in_aoi) stats = <p className="rounded bg-slate-100 p-3 text-sm">{t("polygon.outside")}</p>;
  else {
    const p = q.data;
    stats = (
      <>
        {p.synthetic && <DemoChip />}
        <PolygonSummary p={p} lang={lang} />
      </>
    );
  }

  return (
    <div className="space-y-3" data-testid="polygon-panel">
      {stats}
      <SceneList polygon={polygon} lang={lang} />
      <Disclaimer />
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => download(polygon)} className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50">
          {t("polygon.download")}
        </button>
        {site && (
          <Link
            to={reportPath({ kind: "polygon", site, polygon, lang })}
            target="_blank"
            rel="noopener"
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
            data-testid="polygon-report"
          >
            {t("report.print")}
          </Link>
        )}
        <button type="button" onClick={() => setPolygon(null)} className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50">
          {t("polygon.clear")}
        </button>
      </div>
    </div>
  );
}
