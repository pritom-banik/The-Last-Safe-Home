import maplibregl, {
  type ExpressionSpecification,
  type GeoJSONSource,
  type LayerSpecification,
  type RasterTileSource,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { tileUrl, vectorUrl, type LayersManifest } from "../api/client";
import { DEFAULT_VIEW } from "../config";
import { useApp } from "../store";
import { LAYERS, RAMPS, TRANSECT_RANGE, type LayerId } from "./layerDefs";
import type { Draw } from "./draw";
import { declutter, labelPoint, roughArea } from "./geometry";
import { BASE_STYLE } from "./style";

/** MapLibre layer ids belonging to each app layer (some app layers draw more than one style layer). */
const STYLE_LAYERS: Record<LayerId, string[]> = {
  sar_hh: ["lsh-sar_hh"],
  water: ["lsh-water"],
  floodfreq: ["lsh-floodfreq"],
  motion: ["lsh-motion"],
  score: ["lsh-score"],
  banklines: ["lsh-banklines-landsat", "lsh-banklines-nisar-casing", "lsh-banklines-nisar"],
  transects: ["lsh-transects"],
  buildings: ["lsh-buildings"],
  unions: ["lsh-unions"],
};

/** Vector layers fetched only when switched on (large, off by default). */
const LAZY_VECTORS: LayerId[] = ["transects", "buildings"];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
/** Vector layers on by default, fetched right after the first map frame with tiles (they are not the first thing
 * people look at, and the bank lines are the largest download). */
const DEFERRED_VECTORS = ["banklines", "unions"] as const;
/** The map draws Landsat lines and one NISAR date; the median-of-3 lines are only for the report. */
const MAP_BANK_SOURCES = "landsat,nisar";

const OPACITY_PROP: Record<string, string> = { raster: "raster-opacity", line: "line-opacity", circle: "circle-opacity" };

function viridisByYear(years: number[]): ExpressionSpecification {
  const lo = years[0] ?? 1988;
  const hi = years[years.length - 1] ?? 2026;
  const stops = RAMPS.viridis.flatMap((c, i) => [lo + ((hi - lo) * i) / (RAMPS.viridis.length - 1 || 1), c]);
  return ["interpolate", ["linear"], ["get", "year"], ...stops] as unknown as ExpressionSpecification;
}

function nisarFilter(date: string | null): ExpressionSpecification {
  return ["all", ["==", ["get", "source"], "nisar"], ["==", ["get", "date"], date ?? ""]];
}

function addSiteLayers(map: maplibregl.Map, m: LayersManifest, date: string | null) {
  const site = m.site;
  const bounds = m.bounds;
  const raster = (id: LayerId, opts: { date?: string } = {}) => {
    map.addSource(`lsh-${id}`, {
      type: "raster",
      tiles: [tileUrl(site, id, opts)],
      tileSize: 256,
      bounds,
      minzoom: m.static?.minzoom ?? 8,
      // static edition: tiles exist up to this zoom; MapLibre over-zooms beyond it
      maxzoom: m.static?.maxzoom ?? 16,
    });
    map.addLayer({
      id: `lsh-${id}`,
      type: "raster",
      source: `lsh-${id}`,
      paint: { "raster-resampling": id === "score" || id === "water" ? "nearest" : "linear", "raster-fade-duration": 0 },
    });
  };
  const d = date ?? m.nisar_dates[m.nisar_dates.length - 1];
  if (m.rasters.sar_hh) raster("sar_hh", { date: d });
  if (m.rasters.water) raster("water", { date: d });
  if (m.rasters.floodfreq) raster("floodfreq");
  if (m.rasters.motion) raster("motion");
  if (m.rasters.score) raster("score");

  for (const name of ["banklines", "transects", "buildings", "unions"]) {
    if (!m.vectors[name]) continue;
    // every vector starts empty: on-by-default ones load once the first tiles are drawn (DEFERRED_VECTORS),
    // off-by-default ones when first switched on (LAZY_VECTORS)
    map.addSource(`lsh-v-${name}`, { type: "geojson", data: EMPTY });
  }
  const layers: LayerSpecification[] = [];
  if (m.vectors.banklines) {
    layers.push(
      {
        id: "lsh-banklines-landsat",
        type: "line",
        source: "lsh-v-banklines",
        filter: ["==", ["get", "source"], "landsat"],
        paint: { "line-color": viridisByYear(m.landsat_years), "line-width": 1.5 },
      },
      {
        id: "lsh-banklines-nisar-casing",
        type: "line",
        source: "lsh-v-banklines",
        filter: nisarFilter(d),
        paint: { "line-color": "#111827", "line-width": 4.5 },
      },
      {
        id: "lsh-banklines-nisar",
        type: "line",
        source: "lsh-v-banklines",
        filter: nisarFilter(d),
        paint: { "line-color": "#ffffff", "line-width": 2.5 },
      },
    );
  }
  if (m.vectors.transects) {
    layers.push({
      id: "lsh-transects",
      type: "line",
      source: "lsh-v-transects",
      paint: {
        "line-width": 1.5,
        // transects without a rate (null) fall to 0 → grey
        "line-color": [
          "interpolate",
          ["linear"],
          ["to-number", ["get", "rate_m_yr"], 0],
          -TRANSECT_RANGE,
          RAMPS.transects[0],
          0,
          RAMPS.transects[1],
          TRANSECT_RANGE,
          RAMPS.transects[2],
        ],
      },
    });
  }
  if (m.vectors.buildings) {
    layers.push({
      id: "lsh-buildings",
      type: "circle",
      source: "lsh-v-buildings",
      minzoom: 13,
      paint: { "circle-radius": 3, "circle-color": "#111827", "circle-stroke-color": "#ffffff", "circle-stroke-width": 0.5 },
    });
  }
  if (m.vectors.unions) {
    layers.push({
      id: "lsh-unions",
      type: "line",
      source: "lsh-v-unions",
      paint: { "line-color": "#4b5563", "line-width": 1.5, "line-dasharray": [3, 2] },
    });
  }
  for (const l of layers) map.addLayer(l);
}

function removeSiteLayers(map: maplibregl.Map) {
  const style = map.getStyle();
  for (const l of style.layers ?? []) if (l.id.startsWith("lsh-")) map.removeLayer(l.id);
  for (const s of Object.keys(style.sources ?? {})) if (s.startsWith("lsh-")) map.removeSource(s);
}

interface Props {
  manifest: LayersManifest | undefined;
}

export default function MapView({ manifest }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const drawRef = useRef<Draw | null>(null);
  const drawLoading = useRef<Promise<Draw> | null>(null);
  const [drawReady, setDrawReady] = useState(false);
  const [tileError, setTileError] = useState(false);
  const loadedVectors = useRef(new Set<string>());
  const markerRef = useRef<maplibregl.Marker | null>(null);
  const [ready, setReady] = useState(false);
  const [siteLoaded, setSiteLoaded] = useState<string | null>(null);
  const { t, i18n } = useTranslation();

  const visible = useApp((s) => s.visible);
  const opacity = useApp((s) => s.opacity);
  const date = useApp((s) => s.date);
  const basemap = useApp((s) => s.basemap);
  const tool = useApp((s) => s.tool);
  const point = useApp((s) => s.point);
  const polygon = useApp((s) => s.polygon);
  const requestedView = useApp((s) => s.requestedView);

  // create the map once
  useEffect(() => {
    if (!container.current) return;
    // a requested view (URL, site change) wins; else the last view (coming back from another page)
    const v = useApp.getState().requestedView ?? useApp.getState().view;
    const map = new maplibregl.Map({
      container: container.current,
      style: BASE_STYLE,
      center: v ? [v.lon, v.lat] : DEFAULT_VIEW.center,
      zoom: v?.z ?? DEFAULT_VIEW.zoom,
      attributionControl: { compact: false },
      // no cross-fades: far fewer frames to draw while tiles arrive (big win on phones without fast GPUs)
      fadeDuration: 0,
      // sharp enough on phones, and ~35 % fewer pixels to draw than at a phone's native 1.75–3×
      pixelRatio: Math.min(window.devicePixelRatio || 1, 1.5),
      doubleClickZoom: true,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    const report = () => {
      const c = map.getCenter();
      useApp.getState().setView({ lon: c.lng, lat: c.lat, z: map.getZoom() });
    };
    map.on("moveend", report);
    // our data tiles failing (server asleep, offline): say so once instead of showing a silently empty map
    map.on("error", (e) => {
      const id = (e as { sourceId?: string }).sourceId;
      // a 404 tile is "no data here" (static edition writes no empty tiles), and a cancelled request (the date
      // or view changed before the tile arrived) is not a failure either
      const err = (e as { error?: { status?: number; name?: string; message?: string } }).error;
      const aborted = err?.name === "AbortError" || /abort/i.test(err?.message ?? "");
      if (id?.startsWith("lsh-") && err?.status !== 404 && !aborted) {
        console.warn("map data error", id, err?.message);
        setTileError(true);
      }
    });
    map.on("click", (e) => {
      if (useApp.getState().tool !== "inspect") return;
      useApp.getState().inspect([e.lngLat.lng, e.lngLat.lat]);
    });
    map.on("load", () => {
      report();
      setReady(true);
    });
    return () => {
      drawRef.current?.stop();
      drawRef.current = null;
      drawLoading.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // site layers
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !manifest) return;
    if (siteLoaded === manifest.site) return;
    removeSiteLayers(map);
    addSiteLayers(map, manifest, useApp.getState().date);
    const site = manifest.site;
    map.once("idle", () => {
      for (const name of DEFERRED_VECTORS) {
        const src = map.getSource(`lsh-v-${name}`) as GeoJSONSource | undefined;
        src?.setData(vectorUrl(site, name, name === "banklines" ? { source: MAP_BANK_SOURCES } : {}));
      }
    });
    // draw layers stay on top: terra-draw re-adds its layers on each render; nothing to do here
    setSiteLoaded(manifest.site);
  }, [ready, manifest, siteLoaded]);

  // camera requests (URL on load, site change, reset)
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !requestedView) return;
    map.jumpTo({ center: [requestedView.lon, requestedView.lat], zoom: requestedView.z });
    useApp.getState().requestView(null);
  }, [ready, requestedView]);

  // visibility + opacity; lazy vectors are fetched the first time they are shown
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !siteLoaded) return;
    for (const name of LAZY_VECTORS) {
      const key = `${siteLoaded}:${name}`;
      if (!visible.includes(name) || loadedVectors.current.has(key)) continue;
      const src = map.getSource(`lsh-v-${name}`) as GeoJSONSource | undefined;
      if (!src) continue;
      src.setData(vectorUrl(siteLoaded, name));
      loadedVectors.current.add(key);
    }
    for (const def of LAYERS) {
      const hidden = def.id === "motion" && manifest && !manifest.motion_usable;
      for (const id of STYLE_LAYERS[def.id]) {
        const layer = map.getLayer(id);
        if (!layer) continue;
        map.setLayoutProperty(id, "visibility", visible.includes(def.id) && !hidden ? "visible" : "none");
        const prop = OPACITY_PROP[layer.type];
        if (prop) map.setPaintProperty(id, prop, opacity[def.id]);
      }
    }
  }, [siteLoaded, visible, opacity, manifest]);

  // time slider → dated rasters + highlighted NISAR bank line
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !siteLoaded || !manifest || !date) return;
    for (const id of ["sar_hh", "water"] as const) {
      const src = map.getSource(`lsh-${id}`) as RasterTileSource | undefined;
      const url = tileUrl(manifest.site, id, { date });
      // only when the date really changed: re-setting the same tiles cancels the requests already in flight
      if (src && src.tiles?.[0] !== url) src.setTiles([url]);
    }
    for (const id of ["lsh-banklines-nisar", "lsh-banklines-nisar-casing"]) {
      if (map.getLayer(id)) map.setFilter(id, nisarFilter(date));
    }
  }, [siteLoaded, manifest, date]);

  // basemap
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    map.setLayoutProperty("basemap-map", "visibility", basemap === "map" ? "visible" : "none");
    map.setLayoutProperty("basemap-satellite", "visibility", basemap === "satellite" ? "visible" : "none");
  }, [ready, basemap]);

  // tool → draw mode (the drawing library loads the first time Draw is picked)
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (tool === "draw") map.doubleClickZoom.disable();
    else map.doubleClickZoom.enable();
    map.getCanvas().style.cursor = tool === "draw" ? "crosshair" : "";
    if (tool !== "draw" && !drawRef.current) return;
    drawLoading.current ??= import("./draw").then(({ createDraw }) => {
      const d = createDraw(map, (p) => {
        useApp.getState().setPolygon(p);
        // finished: back to Inspect (the polygon stays on the map). Deferred so the closing double-click
        // is not also taken as an Inspect click or a double-click zoom.
        window.setTimeout(() => useApp.getState().setTool("inspect"), 400);
      });
      drawRef.current = d;
      setDrawReady(true);
      return d;
    });
    void drawLoading.current.then((d) => {
      if (mapRef.current === map) d.setMode(useApp.getState().tool === "draw" ? "polygon" : "static");
    });
  }, [ready, tool]);

  // cleared polygon → clear the drawing
  useEffect(() => {
    if (!polygon && drawRef.current?.enabled) drawRef.current.clear();
  }, [polygon]);

  // inspected point marker
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    if (!point) {
      markerRef.current?.remove();
      markerRef.current = null;
      return;
    }
    if (!markerRef.current) markerRef.current = new maplibregl.Marker({ color: "#111827" });
    markerRef.current.setLngLat(point).addTo(map);
  }, [ready, point]);

  // union labels as HTML markers: browsers shape Bangla text correctly, MapLibre's glyph renderer does not
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !siteLoaded || !manifest?.vectors.unions || !visible.includes("unions")) return;
    let cancelled = false;
    const markers: maplibregl.Marker[] = [];
    const lang = i18n.language === "bn" ? "bn" : "en";
    let order: number[] = [];
    // labels that would overlap a bigger union's label are hidden (and leave the tab order) until there is room
    const tidy = () => {
      const els = markers.map((mk) => mk.getElement());
      const show = declutter(els.map((el) => el.getBoundingClientRect()), order);
      els.forEach((el, i) => {
        el.style.visibility = show[i] ? "" : "hidden";
      });
    };
    fetch(vectorUrl(manifest.site, "unions"))
      .then((r) => r.json())
      .then((fc: GeoJSON.FeatureCollection) => {
        if (cancelled) return;
        fc.features.forEach((f, index) => {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "lsh-union-label";
          el.textContent = String(f.properties?.[`name_${lang}`] ?? f.properties?.name_en ?? "");
          el.addEventListener("click", (ev) => {
            ev.stopPropagation();
            useApp.getState().openUnion(index);
          });
          markers.push(new maplibregl.Marker({ element: el }).setLngLat(labelPoint(f.geometry)).addTo(map));
          el.setAttribute("aria-label", el.textContent); // addTo() sets a generic "Map marker" label
        });
        order = fc.features.map((f, i) => [roughArea(f.geometry), i]).sort((a, b) => b[0] - a[0]).map(([, i]) => i);
        tidy();
        map.on("moveend", tidy);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      map.off("moveend", tidy);
      markers.forEach((mk) => mk.remove());
    };
  }, [siteLoaded, manifest, visible, i18n.language]);

  return (
    <div className="relative h-full w-full">
      <div ref={container} className="h-full w-full" data-testid="map" aria-label={t("app.name")} role="region" />
      {tileError && (
        <div role="status" className="absolute bottom-10 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 rounded bg-slate-900/90 px-3 py-1.5 text-sm text-white" data-testid="tile-error">
          {t("app.tileError")}
          <button type="button" onClick={() => setTileError(false)} aria-label={t("point.close")} className="px-1 text-lg leading-none">
            ×
          </button>
        </div>
      )}
      {tool === "draw" && drawReady && (
        <div data-testid="draw-hint" className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded bg-slate-900/85 px-3 py-1.5 text-sm text-white">
          {t("tools.drawHint")}
        </div>
      )}
    </div>
  );
}
