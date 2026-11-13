/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_STATIC_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "@maplibre/maplibre-gl-compare" {
  import type { Map } from "maplibre-gl";

  export default class Compare {
    constructor(
      a: Map,
      b: Map,
      container: string | HTMLElement,
      options?: { orientation?: "vertical" | "horizontal"; mousemove?: boolean },
    );
    currentPosition?: number;
    setSlider(x: number): void;
    remove(): void;
    on(type: "slideend", fn: (e: { currentPosition: number }) => void): this;
  }
}
