/**
 * Shareable URL state (SPEC §10.1):
 *   ?site=demo&lat=&lon=&z=&layers=score,banklines&date=2026-09-14&lang=bn&mode=compare&pt=lon,lat
 * `pt` (the inspected point) is an addition so "Copy link" reopens the point card (docs/DECISIONS.md).
 */

import { isLang, type Lang } from "./format";

export interface UrlState {
  site?: string;
  lat?: number;
  lon?: number;
  z?: number;
  layers?: string[];
  date?: string;
  lang?: Lang;
  mode?: "compare";
  pt?: [number, number];
}

const num = (s: string | null): number | undefined => {
  if (s == null || s.trim() === "") return undefined;
  const n = Number(s);
  return Number.isFinite(n) ? n : undefined;
};

const ID = /^[a-z0-9_-]{1,40}$/;
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export function decodeUrlState(search: string): UrlState {
  const q = new URLSearchParams(search);
  const out: UrlState = {};
  const site = q.get("site");
  if (site && ID.test(site)) out.site = site;
  const lat = num(q.get("lat"));
  const lon = num(q.get("lon"));
  const z = num(q.get("z"));
  if (lat != null && lon != null && Math.abs(lat) <= 90 && Math.abs(lon) <= 180) {
    out.lat = lat;
    out.lon = lon;
  }
  if (z != null && z >= 0 && z <= 22) out.z = z;
  const layers = q.get("layers");
  if (layers != null) out.layers = layers.split(",").filter((l) => ID.test(l));
  const date = q.get("date");
  if (date && DATE.test(date)) out.date = date;
  const lang = q.get("lang");
  if (isLang(lang)) out.lang = lang;
  if (q.get("mode") === "compare") out.mode = "compare";
  const pt = q.get("pt")?.split(",").map((s) => num(s));
  if (pt && pt.length === 2 && pt[0] != null && pt[1] != null && Math.abs(pt[0]) <= 180 && Math.abs(pt[1]) <= 90) {
    out.pt = [pt[0], pt[1]];
  }
  return out;
}

/** Fixed key order and rounding so links stay short and stable. */
export function encodeUrlState(s: UrlState): string {
  const q = new URLSearchParams();
  if (s.site) q.set("site", s.site);
  if (s.lat != null && s.lon != null) {
    q.set("lat", s.lat.toFixed(5));
    q.set("lon", s.lon.toFixed(5));
  }
  if (s.z != null) q.set("z", String(Math.round(s.z * 100) / 100));
  if (s.layers) q.set("layers", s.layers.join(","));
  if (s.date) q.set("date", s.date);
  if (s.lang) q.set("lang", s.lang);
  if (s.mode) q.set("mode", s.mode);
  if (s.pt) q.set("pt", `${s.pt[0].toFixed(5)},${s.pt[1].toFixed(5)}`);
  // keep commas readable
  return q.toString().replace(/%2C/g, ",");
}
