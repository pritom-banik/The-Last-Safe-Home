/** Shared MapLibre style pieces: basemaps (SPEC §10.3) and the bank-line styles used by every map. */

import type { ExpressionSpecification, StyleSpecification } from "maplibre-gl";
import type { Basemap } from "../store";

/** Tiles appear at once instead of cross-fading (fewer frames to draw on slow devices). */
const NO_FADE = { "raster-fade-duration": 0 } as const;

export const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
    esri: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      maxzoom: 19,
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    },
  },
  layers: [
    { id: "basemap-map", type: "raster", source: "osm", paint: NO_FADE },
    { id: "basemap-satellite", type: "raster", source: "esri", layout: { visibility: "none" }, paint: NO_FADE },
  ],
};

/** Base style showing only the chosen basemap (compare and report maps). */
export function baseStyle(basemap: Basemap): StyleSpecification {
  return {
    ...BASE_STYLE,
    layers: [
      { id: "basemap-map", type: "raster", source: "osm", paint: NO_FADE, layout: { visibility: basemap === "map" ? "visible" : "none" } },
      {
        id: "basemap-satellite",
        type: "raster",
        source: "esri",
        paint: NO_FADE,
        layout: { visibility: basemap === "satellite" ? "visible" : "none" },
      },
    ],
  };
}

/** Bank line of one source + date/year: white 2.5 px on a dark casing. */
export function bankLineLayers(source: string, filter: ExpressionSpecification, prefix: string) {
  return [
    {
      id: `${prefix}-casing`,
      type: "line" as const,
      source,
      filter,
      paint: { "line-color": "#111827", "line-width": 4.5 },
    },
    {
      id: prefix,
      type: "line" as const,
      source,
      filter,
      paint: { "line-color": "#ffffff", "line-width": 2.5 },
    },
  ];
}
