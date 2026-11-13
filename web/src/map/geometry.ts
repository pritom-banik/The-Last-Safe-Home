/** Small client geometry helpers. */

/** A label position inside a (Multi)Polygon: the centre of its largest ring's bounding box, nudged inside if needed. */
export function labelPoint(g: GeoJSON.Geometry): [number, number] {
  const rings: GeoJSON.Position[][] =
    g.type === "Polygon" ? [g.coordinates[0]] : g.type === "MultiPolygon" ? g.coordinates.map((p) => p[0]) : [];
  if (!rings.length) return [0, 0];
  const bbox = (r: GeoJSON.Position[]) => {
    const xs = r.map((p) => p[0]);
    const ys = r.map((p) => p[1]);
    return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  };
  const ring = rings.reduce((a, b) => {
    const [aw, as, ae, an] = bbox(a);
    const [bw, bs, be, bn] = bbox(b);
    return (be - bw) * (bn - bs) > (ae - aw) * (an - as) ? b : a;
  });
  const [w, s, e, n] = bbox(ring);
  const c: [number, number] = [(w + e) / 2, (s + n) / 2];
  if (pointInRing(c, ring)) return c;
  // fall back to the midpoint of the widest horizontal chord through the centre
  const xs: number[] = [];
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > c[1] !== yj > c[1]) xs.push(xi + ((c[1] - yi) * (xj - xi)) / (yj - yi));
  }
  xs.sort((a, b) => a - b);
  return xs.length >= 2 ? [(xs[0] + xs[1]) / 2, c[1]] : c;
}

export function pointInRing([x, y]: [number, number], ring: GeoJSON.Position[]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Planar area of a (Multi)Polygon's outer rings in square degrees: only for ranking shapes by size. */
export function roughArea(g: GeoJSON.Geometry): number {
  const rings = g.type === "Polygon" ? [g.coordinates[0]] : g.type === "MultiPolygon" ? g.coordinates.map((p) => p[0]) : [];
  let total = 0;
  for (const r of rings) {
    let a = 0;
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) a += (r[j][0] + r[i][0]) * (r[j][1] - r[i][1]);
    total += Math.abs(a) / 2;
  }
  return total;
}

export interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

/**
 * Which labels to show: biggest first, each kept only if it does not overlap (with `pad` px) one already kept.
 * `boxes[i]` is label i's screen box; `order` lists label indexes, most important first.
 */
export function declutter(boxes: Box[], order: number[], pad = 2): boolean[] {
  const show = boxes.map(() => false);
  const kept: Box[] = [];
  for (const i of order) {
    const b = boxes[i];
    const hit = kept.some(
      (k) => b.left < k.right + pad && b.right > k.left - pad && b.top < k.bottom + pad && b.bottom > k.top - pad,
    );
    if (!hit) {
      kept.push(b);
      show[i] = true;
    }
  }
  return show;
}
