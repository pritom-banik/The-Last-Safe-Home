/** Typed client for the FastAPI backend (SPEC §9). The client never sends file paths — only site/layer/date. */

import { API_BASE, STATIC_URL } from "../config";
import { lookupPoint, type PointGrid } from "./staticSource";
import type { ClassKey } from "../score";

export interface SiteSummary {
  id: string;
  name: { en: string; bn: string };
  synthetic: boolean;
  center: [number, number];
  zoom: number;
  bounds: [number, number, number, number];
}

export interface RasterLayer {
  pattern?: string;
  path?: string;
  rescale?: [number, number];
  colormap?: string;
}

export interface LayersManifest {
  site: string;
  synthetic: boolean;
  name: { en: string; bn: string };
  center: [number, number];
  zoom: number;
  bounds: [number, number, number, number];
  nisar_dates: string[];
  landsat_years: number[];
  known_gaps: [string, string][];
  motion_usable: boolean;
  bank_date?: string;
  rasters: Record<string, RasterLayer>;
  vectors: Record<string, string>;
  score_weights: Record<string, number>;
  /** present in the static edition (api/static_export.py): pre-rendered tile zooms and point grid spacing */
  static?: { minzoom: number; maxzoom: number; grid_m: number };
}

export interface SiteStats {
  site: string;
  synthetic: boolean;
  land_area_km2?: number;
  land_lost_km2?: { from_year: number; to_year: number; net: number; eroded: number; accreted: number };
  mean_retreat_m_yr?: number | null;
  max_retreat_m_yr?: number | null;
  buildings_total?: number;
  buildings_within_500m?: number;
  nisar_passes?: number;
  nisar_first?: string;
  nisar_last?: string;
  motion_usable?: boolean;
  coherent_land_pct?: number;
}

export interface PointResult {
  site: string;
  in_aoi: boolean;
  in_river: boolean;
  score: number | null;
  class: ClassKey | null;
  years_until_river: { central: number | null; low: number | null; high: number | null; over_50: boolean } | null;
  distance_to_bank_m: number | null;
  retreat_rate_m_yr: number | null;
  retreat_sigma_m_yr: number | null;
  transect_id: number | null;
  flood_frequency: number | null;
  motion_mm: number | null;
  motion_status: "ok" | "masked" | "not_usable";
  components: { H_E: number; H_F: number; H_G: number } | null;
  weights: Record<string, number>;
  data: {
    nisar_passes: number | null;
    last_pass: string | null;
    bank_date: string | null;
    synthetic: boolean;
    /** static edition: the answer is for the grid cell (this many metres) containing the point */
    grid_m?: number;
  };
}

export interface PolygonStats {
  in_aoi: boolean;
  area_km2?: number | null;
  land_area_km2?: number | null;
  area_lost_km2_per_yr?: number | null;
  mean_score?: number | null;
  max_retreat_m_yr?: number | null;
  buildings_total?: number | null;
  buildings_within_100m?: number | null;
  buildings_within_500m?: number | null;
  people_by_class?: Record<ClassKey, number> | null;
  transects?: number | null;
  synthetic: boolean;
}

export interface AreaCheckRow {
  published_year: number;
  published_km2: number;
  landsat_year: number;
  landsat_km2: number;
  diff_km2: number;
  diff_pct: number;
}

export interface RiverOutline {
  river_iou: number | null;
  outline_dist_px_median: number | null;
  outline_dist_px_p75: number | null;
  outline_within_2px_frac: number | null;
  nisar_wetter_frac: number | null;
}

/** validation.json (SPEC §7.11); every part is optional except the status. */
export interface Validation {
  status: "validated" | "not_validated" | string;
  reason?: string;
  accuracy?: {
    n: number;
    confusion: { tp: number; tn: number; fp: number; fn: number };
    overall_accuracy: number;
    kappa: number | null;
  };
  area_check?: {
    island_unions?: string[];
    landsat_island_km2?: Record<string, number>;
    closest_year?: AreaCheckRow[];
    within_15pct?: boolean;
    declining?: boolean;
  };
  sentinel2_check?: {
    status: string;
    nisar_date?: string;
    sentinel2_date?: string;
    agreement?: number;
    water_iou?: number;
    pixel_m?: number;
    river_median3?: RiverOutline;
    within_2px?: boolean;
  };
}

export interface Scene {
  granule: string;
  product: string;
  datetime: string;
  direction: string;
  track: number | string;
  url_asf: string;
  size_mb: number | null;
}

/** Error in the API's standard shape `{"error": {"code", "message"}}`, or a network failure (code "network"). */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch (e) {
    throw new ApiError(0, "network", String(e));
  }
  if (!res.ok) {
    let code = "http_error";
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? message;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

const post = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

const s = encodeURIComponent;

const liveApi = {
  health: () => request<{ status: string; sites: string[] }>("/health"),
  sites: () => request<SiteSummary[]>("/sites"),
  layers: (site: string) => request<LayersManifest>(`/sites/${s(site)}/layers`),
  stats: (site: string) => request<SiteStats>(`/sites/${s(site)}/stats`),
  validation: (site: string) => request<Validation>(`/sites/${s(site)}/validation`),
  point: (site: string, lon: number, lat: number) =>
    request<PointResult>(`/sites/${s(site)}/point?lon=${lon.toFixed(6)}&lat=${lat.toFixed(6)}`),
  polygonStats: (site: string, geometry: GeoJSON.Polygon) =>
    request<PolygonStats>(`/sites/${s(site)}/polygon-stats`, post(geometry)),
  scenes: (geometry: GeoJSON.Polygon) =>
    request<Scene[]>("/scenes", post({ geometry, products: ["GCOV", "GUNW"], start: "2026-06-17", end: null })),
};

// ---------------------------------------------------------------------------------------------- static edition

async function staticJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${STATIC_URL}${path}`);
  } catch (e) {
    throw new ApiError(0, "network", String(e));
  }
  if (!res.ok) throw new ApiError(res.status, res.status === 404 ? "not_found" : "http_error", res.statusText);
  return (await res.json()) as T;
}

const grids = new Map<string, Promise<PointGrid>>();

const unavailable = () =>
  Promise.reject(new ApiError(501, "static_unavailable", "needs the live server (static edition)"));

const staticApi: typeof liveApi = {
  health: async () => ({ status: "ok", sites: (await staticApi.sites()).map((x) => x.id) }),
  sites: () => staticJson<SiteSummary[]>("/sites.json"),
  layers: (site) => staticJson<LayersManifest>(`/sites/${s(site)}/layers.json`),
  stats: (site) => staticJson<SiteStats>(`/sites/${s(site)}/stats.json`),
  validation: (site) => staticJson<Validation>(`/sites/${s(site)}/validation.json`),
  point: async (site, lon, lat) => {
    if (!grids.has(site)) grids.set(site, staticJson<PointGrid>(`/sites/${s(site)}/points.json`));
    let grid: PointGrid;
    try {
      grid = await grids.get(site)!;
    } catch (e) {
      grids.delete(site);
      throw e;
    }
    const p = lookupPoint(grid, lon, lat);
    if (!p) throw new ApiError(404, "outside_aoi", "No data here: this point is outside the study area.");
    return p;
  },
  polygonStats: unavailable,
  scenes: unavailable,
};

/** The live API, or the static files when the app is built with VITE_STATIC_URL. */
export const api = STATIC_URL ? staticApi : liveApi;
export const IS_STATIC = !!STATIC_URL;

/** GeoJSON vector URL; `source` limits bank lines to some sources ("landsat,nisar"). */
export function vectorUrl(site: string, name: string, opts: { source?: string } = {}): string {
  if (STATIC_URL) {
    const variant = opts.source ? `.${opts.source.replace(/,/g, "+")}` : "";
    return `${STATIC_URL}/sites/${s(site)}/vectors/${s(name)}${variant}.geojson`;
  }
  const q = opts.source ? `?source=${s(opts.source)}` : "";
  return `${API_BASE}/sites/${s(site)}/vectors/${s(name)}${q}`;
}

export function tileUrl(site: string, layer: string, opts: { date?: string; year?: number } = {}): string {
  if (STATIC_URL) {
    const key = opts.date ?? (opts.year != null ? String(opts.year) : "static");
    return `${STATIC_URL}/tiles/${s(site)}/${s(layer)}/${key}/{z}/{x}/{y}.png`;
  }
  const q = opts.date ? `?date=${opts.date}` : opts.year != null ? `?year=${opts.year}` : "";
  return `${API_BASE}/tiles/${s(site)}/${s(layer)}/{z}/{x}/{y}.png${q}`;
}
