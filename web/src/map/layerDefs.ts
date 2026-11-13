/** The map's data layers (SPEC §10.3), bottom → top. Basemap is handled separately. */

export type LayerId =
  | "sar_hh"
  | "water"
  | "floodfreq"
  | "motion"
  | "score"
  | "banklines"
  | "transects"
  | "buildings"
  | "unions";

export interface LayerDef {
  id: LayerId;
  kind: "raster" | "vector";
  /** raster layers that follow the time slider */
  dated?: boolean;
  defaultOn: boolean;
  defaultOpacity: number;
}

export const LAYERS: LayerDef[] = [
  { id: "sar_hh", kind: "raster", dated: true, defaultOn: false, defaultOpacity: 0.85 },
  { id: "water", kind: "raster", dated: true, defaultOn: true, defaultOpacity: 0.7 },
  { id: "floodfreq", kind: "raster", defaultOn: false, defaultOpacity: 0.8 },
  { id: "motion", kind: "raster", defaultOn: false, defaultOpacity: 0.8 },
  { id: "score", kind: "raster", defaultOn: true, defaultOpacity: 0.8 },
  { id: "banklines", kind: "vector", defaultOn: true, defaultOpacity: 1 },
  { id: "transects", kind: "vector", defaultOn: false, defaultOpacity: 1 },
  { id: "buildings", kind: "vector", defaultOn: false, defaultOpacity: 1 },
  { id: "unions", kind: "vector", defaultOn: true, defaultOpacity: 1 },
];

export const LAYER_IDS = LAYERS.map((l) => l.id);
export const DEFAULT_VISIBLE: LayerId[] = LAYERS.filter((l) => l.defaultOn).map((l) => l.id);

export function isLayerId(x: string): x is LayerId {
  return (LAYER_IDS as string[]).includes(x);
}

/** Colour ramps shared by map paint and legends (approximating rio-tiler's colormaps for the raster legends). */
export const RAMPS = {
  blues: ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
  rdbu: ["#67001f", "#d6604d", "#f7f7f7", "#4393c3", "#053061"],
  gray: ["#000000", "#ffffff"],
  viridis: ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
  transects: ["#2166ac", "#9ca3af", "#b2182b"],
};

export const WATER_COLOUR = "#2b8cbe";
export const TRANSECT_RANGE = 60; // ±m/yr
