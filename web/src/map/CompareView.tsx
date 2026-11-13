/**
 * Compare mode (SPEC §10.6): swipe between two synced maps.
 * Left = earliest Landsat dry-season water + bank line; right = NISAR water + bank line of the selected date
 * (the latest pass unless the slider moved — docs/DECISIONS.md).
 */

import Compare from "@maplibre/maplibre-gl-compare";
import "@maplibre/maplibre-gl-compare/style.css";
import maplibregl, { type ExpressionSpecification, type RasterTileSource } from "maplibre-gl";
import { useEffect, useRef, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import { tileUrl, vectorUrl, type LayersManifest } from "../api/client";
import { DEFAULT_VIEW } from "../config";
import { formatDate, formatYear, type Lang } from "../format";
import { useApp } from "../store";
import { bankLineLayers, baseStyle } from "./style";

const PANE = { position: "absolute", inset: 0 } as const;

type Side ={ kind: "landsat"; year: number } | { kind: "nisar"; date: string };

function addSide(map: maplibregl.Map, m: LayersManifest, side: Side) {
  const water = side.kind === "landsat" ? "landwater" : "water";
  if (m.rasters[water]) {
    map.addSource("cmp-water", {
      type: "raster",
      tiles: [tileUrl(m.site, water, side.kind === "landsat" ? { year: side.year } : { date: side.date })],
      tileSize: 256,
      bounds: m.bounds,
      minzoom: m.static?.minzoom ?? 8,
      maxzoom: m.static?.maxzoom ?? 16,
    });
    map.addLayer({
      id: "cmp-water",
      type: "raster",
      source: "cmp-water",
      paint: { "raster-opacity": 0.75, "raster-resampling": "nearest" },
    });
  }
  if (m.vectors.banklines) {
    map.addSource("cmp-banks", { type: "geojson", data: vectorUrl(m.site, "banklines") });
    for (const l of bankLineLayers("cmp-banks", bankFilter(side), "cmp-bank")) map.addLayer(l);
  }
}

function bankFilter(side: Side): ExpressionSpecification {
  return side.kind === "landsat"
    ? ["all", ["==", ["get", "source"], "landsat"], ["==", ["get", "year"], side.year]]
    : ["all", ["==", ["get", "source"], "nisar"], ["==", ["get", "date"], side.date]];
}

export default function CompareView({ manifest }: { manifest: LayersManifest }) {
  const { t, i18n } = useTranslation();
  const lang = (i18n.language === "bn" ? "bn" : "en") as Lang;
  const wrapper = useRef<HTMLDivElement>(null);
  const leftEl = useRef<HTMLDivElement>(null);
  const rightEl = useRef<HTMLDivElement>(null);
  const maps = useRef<{ left: maplibregl.Map; right: maplibregl.Map; compare: Compare } | null>(null);
  const date = useApp((s) => s.date);
  const basemap = useApp((s) => s.basemap);

  const year = manifest.landsat_years[0];
  const nisarDate = date && manifest.nisar_dates.includes(date) ? date : manifest.nisar_dates[manifest.nisar_dates.length - 1];

  // build the two maps once per site
  useEffect(() => {
    if (!wrapper.current || !leftEl.current || !rightEl.current) return;
    const v = useApp.getState().view;
    const opts = {
      style: baseStyle(useApp.getState().basemap),
      center: (v ? [v.lon, v.lat] : manifest.center ?? DEFAULT_VIEW.center) as [number, number],
      zoom: v?.z ?? manifest.zoom,
      attributionControl: false as const,
    };
    const left = new maplibregl.Map({ ...opts, container: leftEl.current });
    const right = new maplibregl.Map({ ...opts, container: rightEl.current, attributionControl: { compact: true } });
    right.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    const startDate = useApp.getState().date;
    left.on("load", () => addSide(left, manifest, { kind: "landsat", year }));
    right.on("load", () =>
      addSide(right, manifest, {
        kind: "nisar",
        date: startDate && manifest.nisar_dates.includes(startDate) ? startDate : manifest.nisar_dates[manifest.nisar_dates.length - 1],
      }),
    );
    const compare = new Compare(left, right, wrapper.current);
    // the swipe handle: keyboard reachable (arrow keys move it in 5 % steps)
    const handle = wrapper.current.querySelector<HTMLElement>(".compare-swiper-vertical");
    if (handle) {
      handle.tabIndex = 0;
      handle.setAttribute("role", "separator");
      handle.setAttribute("aria-orientation", "vertical");
    }
    maps.current = { left, right, compare };
    return () => {
      // hand the camera back to the main map
      const c = right.getCenter();
      useApp.getState().requestView({ lon: c.lng, lat: c.lat, z: right.getZoom() });
      compare.remove();
      left.remove();
      right.remove();
      maps.current = null;
    };
  }, [manifest, year]);

  // camera requests (Reset view) move the compare maps too; the main map clears the request
  const requestedView = useApp((s) => s.requestedView);
  useEffect(() => {
    if (requestedView) maps.current?.right.jumpTo({ center: [requestedView.lon, requestedView.lat], zoom: requestedView.z });
  }, [requestedView]);

  // Esc leaves compare mode
  useEffect(() => {
    const onEsc = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") useApp.getState().setMode(null);
    };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, []);

  // slider date → right side
  useEffect(() => {
    const m = maps.current;
    if (!m || !m.right.isStyleLoaded()) return;
    (m.right.getSource("cmp-water") as RasterTileSource | undefined)?.setTiles([tileUrl(manifest.site, "water", { date: nisarDate })]);
    for (const id of ["cmp-bank", "cmp-bank-casing"]) {
      if (m.right.getLayer(id)) m.right.setFilter(id, bankFilter({ kind: "nisar", date: nisarDate }));
    }
  }, [manifest.site, nisarDate]);

  // basemap
  useEffect(() => {
    const m = maps.current;
    if (!m) return;
    for (const map of [m.left, m.right]) {
      if (!map.isStyleLoaded()) continue;
      map.setLayoutProperty("basemap-map", "visibility", basemap === "map" ? "visible" : "none");
      map.setLayoutProperty("basemap-satellite", "visibility", basemap === "satellite" ? "visible" : "none");
    }
  }, [basemap]);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const m = maps.current;
    if (!m || !(e.target as HTMLElement).classList.contains("compare-swiper-vertical")) return;
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    e.stopPropagation();
    const w = wrapper.current?.clientWidth ?? 0;
    const pos = (m.compare.currentPosition ?? w / 2) + (e.key === "ArrowLeft" ? -0.05 : 0.05) * w;
    m.compare.setSlider(Math.max(0, Math.min(w, pos)));
  };

  const label = "pointer-events-none absolute top-3 z-10 rounded bg-slate-900/85 px-3 py-1.5 text-sm font-semibold text-white";
  return (
    <div className="absolute inset-0 z-[5] bg-slate-200" data-testid="compare" onKeyDown={onKey}>
      <div ref={wrapper} className="absolute inset-0" aria-label={t("compare.label")} role="group">
        {/* inline position: maplibre-gl.css (loaded later, with the lazy map chunk) sets .maplibregl-map
            to position: relative, which would collapse these panes to zero height */}
        <div ref={leftEl} style={PANE} data-testid="compare-left" />
        <div ref={rightEl} style={PANE} data-testid="compare-right" />
      </div>
      <div className={`${label} left-3`} data-testid="compare-label-left">
        {t("compare.left", { year: formatYear(year, lang) })}
      </div>
      <div className={`${label} right-16`} data-testid="compare-label-right">
        {t("compare.right", { date: formatDate(nisarDate, lang) })}
      </div>
      <button
        type="button"
        onClick={() => useApp.getState().setMode(null)}
        className="absolute bottom-8 left-1/2 z-10 -translate-x-1/2 rounded bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-lg hover:bg-slate-700"
        data-testid="compare-exit"
      >
        {t("compare.exit")}
      </button>
    </div>
  );
}
