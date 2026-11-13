/**
 * Printable one-page A4 report (SPEC §10.7): /report?site=&lon=&lat=  or  &polygon=<encoded>.
 * Plain HTML + print CSS (browser print-to-PDF), so Bangla text is shaped by the browser.
 * The map is rendered once with MapLibre (preserveDrawingBuffer) and swapped for a PNG (canvas.toDataURL).
 */

import maplibregl, { type ExpressionSpecification, type LngLatBoundsLike } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, tileUrl, vectorUrl, type LayersManifest } from "../api/client";
import { useLayers, usePoint, usePolygonStats, useSites } from "../api/hooks";
import { formatDate, type Lang } from "../format";
import { bankLineLayers, baseStyle } from "../map/style";
import { Credits } from "../pages/Credits";
import { PointSummary } from "../panels/PointCard";
import { PolygonSummary } from "../panels/PolygonPanel";
import { DemoChip, Disclaimer } from "../panels/common";
import { Link, href } from "../router";
import { encodeUrlState } from "../urlState";
import { parseReport, type ReportTarget } from "./reportUrl";

const MAP_W = 720;
const MAP_H = 400;

function bbox(p: GeoJSON.Polygon): [number, number, number, number] {
  const xs = p.coordinates[0].map((c) => c[0]);
  const ys = p.coordinates[0].map((c) => c[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

/** Static map: score + water + today's bank line + the point or polygon, turned into an image when loaded. */
function ReportMap({ manifest, target }: { manifest: LayersManifest; target: ReportTarget }) {
  const { t } = useTranslation();
  const el = useRef<HTMLDivElement>(null);
  const [img, setImg] = useState<string | null>(null);

  useEffect(() => {
    if (!el.current) return;
    const center: [number, number] = target.kind === "point" ? [target.lon, target.lat] : manifest.center;
    const map = new maplibregl.Map({
      container: el.current,
      style: baseStyle("map"),
      center,
      zoom: target.kind === "point" ? 14 : manifest.zoom,
      interactive: false,
      attributionControl: false,
      preserveDrawingBuffer: true,
      fadeDuration: 0,
    });
    if (target.kind === "polygon") map.fitBounds(bbox(target.polygon) as LngLatBoundsLike, { padding: 40, duration: 0, maxZoom: 16 });
    let done = false;
    const snapshot = () => {
      if (done) return;
      done = true;
      try {
        setImg(map.getCanvas().toDataURL("image/png"));
        map.remove();
      } catch {
        /* tainted canvas (a tile server without CORS): keep the live map, it prints too */
      }
    };
    map.on("load", () => {
      const date = manifest.nisar_dates[manifest.nisar_dates.length - 1];
      const bankDate = manifest.bank_date ?? date;
      const raster = (id: string, layer: string, opts: { date?: string }, opacity: number) => {
        if (!manifest.rasters[layer]) return;
        map.addSource(id, { type: "raster", tiles: [tileUrl(manifest.site, layer, opts)], tileSize: 256, bounds: manifest.bounds });
        map.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": opacity, "raster-resampling": "nearest" } });
      };
      raster("r-water", "water", { date }, 0.6);
      raster("r-score", "score", {}, 0.75);
      if (manifest.vectors.banklines) {
        map.addSource("r-banks", { type: "geojson", data: vectorUrl(manifest.site, "banklines", { source: "nisar-median3" }) });
        const filter: ExpressionSpecification = ["all", ["==", ["get", "source"], "nisar-median3"], ["==", ["get", "date"], bankDate]];
        for (const l of bankLineLayers("r-banks", filter, "r-bank")) map.addLayer(l);
      }
      if (target.kind === "point") {
        map.addSource("r-pt", { type: "geojson", data: { type: "Point", coordinates: [target.lon, target.lat] } });
        map.addLayer({
          id: "r-pt",
          type: "circle",
          source: "r-pt",
          paint: { "circle-radius": 7, "circle-color": "#111827", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 },
        });
      } else {
        map.addSource("r-poly", { type: "geojson", data: target.polygon });
        map.addLayer({ id: "r-poly-fill", type: "fill", source: "r-poly", paint: { "fill-color": "#7c3aed", "fill-opacity": 0.12 } });
        map.addLayer({ id: "r-poly", type: "line", source: "r-poly", paint: { "line-color": "#7c3aed", "line-width": 2.5 } });
      }
      // first idle after the data layers were added = all tiles drawn
      map.once("idle", snapshot);
    });
    const fallback = window.setTimeout(snapshot, 20_000);
    return () => {
      window.clearTimeout(fallback);
      if (!done) map.remove();
    };
  }, [manifest, target]);

  return (
    <figure className="m-0">
      <div className="relative overflow-hidden rounded border border-slate-300" style={{ width: "100%", maxWidth: MAP_W, aspectRatio: `${MAP_W} / ${MAP_H}` }}>
        {img ? (
          <img src={img} alt={t("report.mapAlt")} className="block h-full w-full" data-testid="report-map-image" />
        ) : (
          // inline: maplibre-gl.css would otherwise turn this into position: relative (zero height)
          <div ref={el} style={{ position: "absolute", inset: 0 }} data-testid="report-map-live" />
        )}
      </div>
      <figcaption className="mt-1 text-[11px] text-slate-500">{t("report.mapCaption")}</figcaption>
    </figure>
  );
}

function PointBody({ target, lang }: { target: Extract<ReportTarget, { kind: "point" }>; lang: Lang }) {
  const { t } = useTranslation();
  const q = usePoint(target.site, [target.lon, target.lat]);
  if (q.isPending) return <div className="h-40 animate-pulse rounded bg-slate-100" />;
  if (q.isError) {
    const outside = q.error instanceof ApiError && q.error.code === "outside_aoi";
    return <p role="alert">{outside ? t("point.errorOutside") : t("point.errorGeneric")}</p>;
  }
  return (
    <div className="space-y-2" data-testid="report-point">
      {q.data.data.synthetic && <DemoChip />}
      <PointSummary p={q.data} lang={lang} />
    </div>
  );
}

function PolygonBody({ target, lang }: { target: Extract<ReportTarget, { kind: "polygon" }>; lang: Lang }) {
  const { t } = useTranslation();
  const q = usePolygonStats(target.site, target.polygon);
  if (q.isPending) return <div className="h-40 animate-pulse rounded bg-slate-100" />;
  if (q.isError) return <p role="alert">{t("polygon.errorGeneric")}</p>;
  if (!q.data.in_aoi) return <p>{t("polygon.outside")}</p>;
  return (
    <div className="space-y-2" data-testid="report-polygon">
      {q.data.synthetic && <DemoChip />}
      <PolygonSummary p={q.data} lang={lang} />
    </div>
  );
}

export default function ReportPage() {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const target = useMemo(() => parseReport(window.location.search), []);
  const sites = useSites();
  const layers = useLayers(target?.site ?? null);
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  useEffect(() => {
    document.title = `${t("report.title")} — ${t("app.name")}`;
  }, [t]);

  if (!target) {
    return (
      <main className="mx-auto max-w-2xl p-6">
        <p role="alert">{t("report.bad")}</p>
        <Link to="/map" className="text-sky-700 underline">
          {t("nav.backToMap")}
        </Link>
      </main>
    );
  }
  const site = sites.data?.find((s) => s.id === target.site);
  const manifest = layers.data?.site === target.site ? layers.data : undefined;
  const back =
    target.kind === "point"
      ? `/map?${encodeUrlState({ site: target.site, lon: target.lon, lat: target.lat, z: 14, lang, pt: [target.lon, target.lat] })}`
      : `/map?${encodeUrlState({ site: target.site, lang })}`;
  const backAbs = `${window.location.origin}${href(back)}`;

  return (
    <div className="min-h-full bg-slate-100 print:bg-white">
      <div className="no-print sticky top-0 z-10 flex items-center gap-3 bg-slate-900 px-4 py-2 text-sm text-white">
        <Link to={back} className="hover:underline">
          ← {t("nav.backToMap")}
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="ml-auto rounded bg-white px-3 py-1 font-semibold text-slate-900 hover:bg-slate-200"
          data-testid="report-print"
        >
          {t("report.printNow")}
        </button>
      </div>
      <main className="report-sheet mx-auto my-4 space-y-4 bg-white p-8 shadow print:my-0 print:p-0 print:shadow-none" data-testid="report">
        <header className="flex items-start justify-between gap-4 border-b border-slate-300 pb-3">
          <div>
            <h1 className="text-2xl font-bold">{t("app.name")}</h1>
            <p className="text-sm text-slate-600">{t("app.tagline")}</p>
          </div>
          <div className="text-right text-sm">
            <div className="font-semibold">{site ? site.name[lang] ?? site.name.en : target.site}</div>
            <div className="text-slate-600">
              {t("report.generated", { date: formatDate(today, lang, "long") })}
            </div>
          </div>
        </header>
        {manifest?.synthetic && (
          <p className="rounded bg-red-700 px-3 py-1.5 text-center text-sm font-bold text-white">{t("app.demoBanner")}</p>
        )}
        <h2 className="text-lg font-semibold">{target.kind === "point" ? t("report.pointTitle") : t("report.polygonTitle")}</h2>
        {manifest ? <ReportMap manifest={manifest} target={target} /> : <div className="h-64 animate-pulse rounded bg-slate-100" />}
        <section className="text-sm">
          {target.kind === "point" ? <PointBody target={target} lang={lang} /> : <PolygonBody target={target} lang={lang} />}
        </section>
        <section className="text-sm">
          <h3 className="mb-1 font-semibold">{t("report.methodTitle")}</h3>
          <ol className="list-decimal space-y-0.5 pl-5">
            <li>{t("report.method1")}</li>
            <li>{t("report.method2")}</li>
            <li>{t("report.method3")}</li>
          </ol>
        </section>
        <Disclaimer />
        <section className="text-xs text-slate-600">
          <h3 className="mb-1 font-semibold">{t("credits.title")}</h3>
          <Credits compact />
        </section>
        <p className="break-all text-xs text-slate-600">
          {t("report.link")}: <a href={backAbs}>{backAbs}</a>
        </p>
      </main>
    </div>
  );
}
