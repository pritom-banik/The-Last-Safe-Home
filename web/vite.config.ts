/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// the config runs in Node; the app tsconfig has no Node types
declare const process: { env: Record<string, string | undefined> };

export default defineConfig({
  // sub-path deploys (GitHub Pages: /<repo>/); the router and asset URLs follow it
  base: process.env.VITE_BASE || "/",
  plugins: [react()],
  // /method imports ../docs/METHOD*.md at build time: let the dev server read the repo root
  server: { port: 5173, fs: { allow: [".."] } },
  build: {
    sourcemap: true,
    // maplibre is most of the bundle and changes rarely: keep it in its own cached chunk (terra-draw loads on demand)
    rollupOptions: { output: { manualChunks: { map: ["maplibre-gl"] } } },
    chunkSizeWarningLimit: 1100,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
