import { describe, expect, it } from "vitest";
import { staticBase } from "../config";
import { lookupPoint, type PointGrid } from "./staticSource";

// 2 × 3 grid of 0.1° cells from (90.0, 22.2) down to 22.0; cell 0 is outside the study area,
// cell 1 is river, cell 4 is land
const grid: PointGrid = {
  site: "demo",
  west: 90.0,
  north: 22.2,
  dlon: 0.1,
  dlat: 0.1,
  cols: 3,
  rows: 2,
  grid_m: 100,
  weights: { erosion: 0.6, flood: 0.3, motion: 0.1 },
  data: { nisar_passes: 10, last_pass: "2026-10-15", bank_date: "2026-10-15", synthetic: true },
  motion_status: null,
  idx: [1, 4],
  river: [1, 0],
  river_f: [0.9, null],
  columns: ["score", "yc", "yl", "yh", "o50", "d", "r", "sg", "tid", "f", "m", "he", "hf", "hg"],
  values: [[null, 53], [null, 10.8], [null, 9], [null, 13.4], [null, 0], [null, 410], [null, 38], [null, 7.5], [null, 117], [null, 0.42], [null, null], [null, 0.666], [null, 0.42], [null, 0]],
};

describe("static point grid", () => {
  it("answers a land cell like the API", () => {
    const p = lookupPoint(grid, 90.15, 22.05)!; // row 1, col 1 -> cell 4
    expect(p.in_river).toBe(false);
    expect(p.score).toBe(53);
    expect(p.class).toBe("high");
    expect(p.years_until_river).toEqual({ central: 10.8, low: 9, high: 13.4, over_50: false });
    expect(p.distance_to_bank_m).toBe(410);
    expect(p.motion_status).toBe("masked");
    expect(p.components).toEqual({ H_E: 0.666, H_F: 0.42, H_G: 0 });
    expect(p.data.grid_m).toBe(100);
  });

  it("answers river cells and nothing outside", () => {
    const r = lookupPoint(grid, 90.15, 22.15)!; // cell 1
    expect(r.in_river).toBe(true);
    expect(r.score).toBeNull();
    expect(r.flood_frequency).toBe(0.9);
    expect(lookupPoint(grid, 90.05, 22.15)).toBeNull(); // cell 0: not in idx
    expect(lookupPoint(grid, 89.9, 22.1)).toBeNull(); // west of the grid
    expect(lookupPoint(grid, 90.1, 21.9)).toBeNull(); // south of the grid
  });

  it("reports motion as not usable site-wide", () => {
    expect(lookupPoint({ ...grid, motion_status: "not_usable" }, 90.15, 22.05)!.motion_status).toBe("not_usable");
  });
});

describe("staticBase", () => {
  it("is off unless set", () => {
    expect(staticBase(undefined)).toBeNull();
    expect(staticBase(" ")).toBeNull();
    expect(staticBase("/static/")).toBe("/static");
  });
});
