/**
 * Static fallback (SPEC §14 phase 10): answers the API's questions from files written by
 * `python -m api.static_export` (see that module for the layout). Used when the app is built with
 * VITE_STATIC_URL. Clicks are answered from a precomputed point grid; polygon statistics and the NISAR scene
 * search need the live API and fail with code "static_unavailable".
 */

import type { ClassKey } from "../score";
import { scoreClass } from "../score";

/** Grid of precomputed point answers (sites/<site>/points.json). */
export interface PointGrid {
  site: string;
  west: number;
  north: number;
  dlon: number;
  dlat: number;
  cols: number;
  rows: number;
  grid_m: number;
  weights: Record<string, number>;
  data: { nisar_passes: number | null; last_pass: string | null; bank_date: string | null; synthetic: boolean };
  motion_status: "not_usable" | null;
  idx: number[];
  river: number[];
  river_f: (number | null)[];
  columns: string[];
  values: (number | null)[][];
}

export interface StaticPoint {
  site: string;
  in_aoi: true;
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
  data: PointGrid["data"] & { grid_m: number };
}

/** Binary search in the sorted list of inside-the-study-area cell indexes. */
function position(sorted: number[], v: number): number {
  let lo = 0;
  let hi = sorted.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] === v) return mid;
    if (sorted[mid] < v) lo = mid + 1;
    else hi = mid - 1;
  }
  return -1;
}

/** The precomputed answer for the grid cell containing (lon, lat); null when outside the study area. */
export function lookupPoint(g: PointGrid, lon: number, lat: number): StaticPoint | null {
  const c = Math.floor((lon - g.west) / g.dlon);
  const r = Math.floor((g.north - lat) / g.dlat);
  if (c < 0 || r < 0 || c >= g.cols || r >= g.rows) return null;
  const k = position(g.idx, r * g.cols + c);
  if (k < 0) return null;
  const col = (name: string) => g.values[g.columns.indexOf(name)]?.[k] ?? null;
  const data = { ...g.data, grid_m: g.grid_m };
  const base = { site: g.site, in_aoi: true as const, weights: g.weights, data };
  if (g.river[k]) {
    return {
      ...base,
      in_river: true,
      score: null,
      class: null,
      years_until_river: null,
      distance_to_bank_m: null,
      retreat_rate_m_yr: null,
      retreat_sigma_m_yr: null,
      transect_id: null,
      flood_frequency: g.river_f[k],
      motion_mm: null,
      motion_status: g.motion_status ?? "masked",
      components: null,
    };
  }
  const m = col("m");
  const score = col("score");
  return {
    ...base,
    in_river: false,
    score,
    class: scoreClass(score),
    years_until_river: { central: col("yc"), low: col("yl"), high: col("yh"), over_50: col("o50") === 1 },
    distance_to_bank_m: col("d"),
    retreat_rate_m_yr: col("r"),
    retreat_sigma_m_yr: col("sg"),
    transect_id: col("tid"),
    flood_frequency: col("f"),
    motion_mm: m,
    motion_status: g.motion_status ?? (m == null ? "masked" : "ok"),
    components: { H_E: col("he") ?? 0, H_F: col("hf") ?? 0, H_G: col("hg") ?? 0 },
  };
}
