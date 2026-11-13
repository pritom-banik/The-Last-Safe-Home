import { describe, expect, it } from "vitest";
import { declutter, roughArea } from "./geometry";

describe("union label decluttering", () => {
  it("keeps the first of two overlapping labels and any label clear of the others", () => {
    const boxes = [
      { left: 0, top: 0, right: 60, bottom: 20 },
      { left: 50, top: 10, right: 110, bottom: 30 }, // overlaps 0
      { left: 200, top: 0, right: 260, bottom: 20 },
    ];
    expect(declutter(boxes, [0, 1, 2])).toEqual([true, false, true]);
    expect(declutter(boxes, [1, 0, 2])).toEqual([false, true, true]);
  });

  it("ranks polygons by area", () => {
    const sq = (s: number): GeoJSON.Polygon => ({ type: "Polygon", coordinates: [[[0, 0], [s, 0], [s, s], [0, s], [0, 0]]] });
    expect(roughArea(sq(2))).toBeCloseTo(4);
    expect(roughArea(sq(2))).toBeGreaterThan(roughArea(sq(1)));
  });
});
