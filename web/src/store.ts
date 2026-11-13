/** App state (zustand). URL sync lives in useUrlSync; this module stays free of side effects. */

import { create } from "zustand";
import type { Lang } from "./format";
import { DEFAULT_VISIBLE, LAYERS, type LayerId } from "./map/layerDefs";

export type Tool = "inspect" | "draw";
export type Basemap = "map" | "satellite";
export type Mode = "compare" | null;
export type Drawer = null | { kind: "point" } | { kind: "polygon" } | { kind: "union"; index: number };

export interface View {
  lon: number;
  lat: number;
  z: number;
}

interface State {
  site: string | null;
  /** view requested from outside (URL on load, site change); the map flies there and clears it */
  requestedView: View | null;
  view: View | null;
  visible: LayerId[];
  opacity: Record<LayerId, number>;
  date: string | null;
  lang: Lang;
  tool: Tool;
  basemap: Basemap;
  point: [number, number] | null;
  polygon: GeoJSON.Polygon | null;
  drawer: Drawer;
  sidebarOpen: boolean;
  /** swipe comparison of the earliest Landsat year and the selected NISAR date (SPEC §10.6) */
  mode: Mode;

  setSite: (site: string) => void;
  setView: (v: View) => void;
  requestView: (v: View | null) => void;
  toggleLayer: (id: LayerId) => void;
  setOpacity: (id: LayerId, value: number) => void;
  setDate: (date: string) => void;
  setLang: (lang: Lang) => void;
  setTool: (tool: Tool) => void;
  setBasemap: (b: Basemap) => void;
  inspect: (pt: [number, number]) => void;
  setPolygon: (p: GeoJSON.Polygon | null) => void;
  openUnion: (index: number) => void;
  closeDrawer: () => void;
  setSidebarOpen: (open: boolean) => void;
  setMode: (mode: Mode) => void;
}

const defaultOpacity = Object.fromEntries(LAYERS.map((l) => [l.id, l.defaultOpacity])) as Record<LayerId, number>;

export const useApp = create<State>((set) => ({
  site: null,
  requestedView: null,
  view: null,
  visible: DEFAULT_VISIBLE,
  opacity: defaultOpacity,
  date: null,
  lang: "en",
  tool: "inspect",
  basemap: "map",
  point: null,
  polygon: null,
  drawer: null,
  sidebarOpen: true,
  mode: null,

  setSite: (site) =>
    set((s) => (s.site === site ? s : { site, date: null, point: null, polygon: null, drawer: null, mode: null })),
  setView: (view) => set({ view }),
  requestView: (requestedView) => set({ requestedView }),
  toggleLayer: (id) =>
    set((s) => ({ visible: s.visible.includes(id) ? s.visible.filter((v) => v !== id) : [...s.visible, id] })),
  setOpacity: (id, value) => set((s) => ({ opacity: { ...s.opacity, [id]: value } })),
  setDate: (date) => set({ date }),
  setLang: (lang) => set({ lang }),
  // starting a drawing closes the point card (and its marker) so the drawer does not cover the area being drawn
  // picking a tool leaves compare mode
  setTool: (tool) =>
    set((s) =>
      tool === "draw" && s.drawer?.kind !== "polygon"
        ? { tool, mode: null, drawer: null, point: null }
        : { tool, mode: null },
    ),
  setBasemap: (basemap) => set({ basemap }),
  inspect: (point) => set({ point, drawer: { kind: "point" } }),
  setPolygon: (polygon) => set({ polygon, drawer: polygon ? { kind: "polygon" } : null }),
  openUnion: (index) => set({ drawer: { kind: "union", index } }),
  closeDrawer: () => set({ drawer: null, point: null }),
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  // compare mode has no point card or drawing: close the drawer and go back to Inspect
  setMode: (mode) => set(mode ? { mode, drawer: null, point: null, tool: "inspect" } : { mode }),
}));
