/**
 * Report links (SPEC §10.7): /report?site=&lon=&lat=  or  /report?site=&polygon=<encoded>.
 * The polygon is its outer ring as JSON with 5-decimal coordinates (~1 m), closing point dropped.
 */

import { isLang, type Lang } from "../format";

export type ReportTarget =
  | { kind: "point"; site: string; lon: number; lat: number; lang?: Lang }
  | { kind: "polygon"; site: string; polygon: GeoJSON.Polygon; lang?: Lang };

const ID = /^[a-z0-9_-]{1,40}$/;
const MAX_VERTICES = 500;

const r5 = (v: number) => Math.round(v * 1e5) / 1e5;

export function encodePolygon(p: GeoJSON.Polygon): string {
  const ring = p.coordinates[0] ?? [];
  const open =
    ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]
      ? ring.slice(0, -1)
      : ring;
  return JSON.stringify(open.map(([x, y]) => [r5(x), r5(y)]));
}

export function decodePolygon(s: string | null): GeoJSON.Polygon | null {
  if (!s) return null;
  let raw: unknown;
  try {
    raw = JSON.parse(s);
  } catch {
    return null;
  }
  if (!Array.isArray(raw) || raw.length < 3 || raw.length > MAX_VERTICES) return null;
  const ring: [number, number][] = [];
  for (const pt of raw) {
    if (!Array.isArray(pt) || pt.length !== 2) return null;
    const [x, y] = pt;
    if (typeof x !== "number" || typeof y !== "number" || Math.abs(x) > 180 || Math.abs(y) > 90) return null;
    ring.push([x, y]);
  }
  ring.push([ring[0][0], ring[0][1]]);
  return { type: "Polygon", coordinates: [ring] };
}

export function reportPath(t: ReportTarget): string {
  const q = new URLSearchParams();
  q.set("site", t.site);
  if (t.kind === "point") {
    q.set("lon", t.lon.toFixed(5));
    q.set("lat", t.lat.toFixed(5));
  } else {
    q.set("polygon", encodePolygon(t.polygon));
  }
  if (t.lang) q.set("lang", t.lang);
  return `/report?${q.toString()}`;
}

export function parseReport(search: string): ReportTarget | null {
  const q = new URLSearchParams(search);
  const site = q.get("site");
  if (!site || !ID.test(site)) return null;
  const lang = q.get("lang");
  const l = isLang(lang) ? lang : undefined;
  const polygon = decodePolygon(q.get("polygon"));
  if (polygon) return { kind: "polygon", site, polygon, lang: l };
  const lon = Number(q.get("lon"));
  const lat = Number(q.get("lat"));
  if (q.get("lon") && q.get("lat") && Number.isFinite(lon) && Number.isFinite(lat) && Math.abs(lon) <= 180 && Math.abs(lat) <= 90) {
    return { kind: "point", site, lon, lat, lang: l };
  }
  return null;
}
