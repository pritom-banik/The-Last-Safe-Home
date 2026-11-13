/**
 * Polygon drawing (SPEC §10.5) with Terra Draw. Loaded on demand the first time the Draw tool is picked, so the
 * drawing library is not part of the first page load (SPEC §10.9).
 */

import type maplibregl from "maplibre-gl";
import { TerraDraw, TerraDrawPolygonMode } from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";

export type Draw = TerraDraw;

export function createDraw(map: maplibregl.Map, onFinish: (polygon: GeoJSON.Polygon) => void): TerraDraw {
  const draw = new TerraDraw({
    adapter: new TerraDrawMapLibreGLAdapter({ map }),
    modes: [
      new TerraDrawPolygonMode({
        styles: { fillColor: "#7c3aed", fillOpacity: 0.15, outlineColor: "#7c3aed", outlineWidth: 2 },
      }),
    ],
  });
  draw.start();
  draw.on("finish", (id) => {
    const f = draw.getSnapshotFeature(id);
    if (!f || f.geometry.type !== "Polygon") return;
    // one polygon at a time
    const others = draw
      .getSnapshot()
      .filter((x) => x.id !== id)
      .map((x) => x.id!);
    if (others.length) draw.removeFeatures(others);
    onFinish(f.geometry as GeoJSON.Polygon);
  });
  return draw;
}
