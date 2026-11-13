import { describe, expect, it } from "vitest";
import { routeOf } from "../router";
import { decodePolygon, encodePolygon, parseReport, reportPath } from "./reportUrl";

const square: GeoJSON.Polygon = {
  type: "Polygon",
  coordinates: [
    [
      [90.6612345678, 22.64],
      [90.67, 22.64],
      [90.67, 22.65],
      [90.66, 22.65],
      [90.6612345678, 22.64],
    ],
  ],
};

describe("report links", () => {
  it("round-trips a point", () => {
    const path = reportPath({ kind: "point", site: "demo", lon: 90.663, lat: 22.65, lang: "bn" });
    expect(path).toBe("/report?site=demo&lon=90.66300&lat=22.65000&lang=bn");
    expect(parseReport(path.split("?")[1])).toEqual({ kind: "point", site: "demo", lon: 90.663, lat: 22.65, lang: "bn" });
  });

  it("round-trips a polygon with 5-decimal coordinates and a closed ring", () => {
    const path = reportPath({ kind: "polygon", site: "manpura", polygon: square });
    const t = parseReport(path.split("?")[1]);
    expect(t?.kind).toBe("polygon");
    if (t?.kind !== "polygon") return;
    const ring = t.polygon.coordinates[0];
    expect(ring).toHaveLength(5);
    expect(ring[0]).toEqual([90.66123, 22.64]);
    expect(ring[4]).toEqual(ring[0]);
    expect(encodePolygon(t.polygon)).toBe(encodePolygon(square));
  });

  it("rejects bad input", () => {
    expect(parseReport("lon=1&lat=2")).toBeNull();
    expect(parseReport("site=../x&lon=1&lat=2")).toBeNull();
    expect(parseReport("site=demo&lon=500&lat=2")).toBeNull();
    expect(parseReport("site=demo")).toBeNull();
    expect(decodePolygon("[[1,2],[3,4]]")).toBeNull();
    expect(decodePolygon('[[1,2],[3,"x"],[5,6]]')).toBeNull();
    expect(decodePolygon("not json")).toBeNull();
  });
});

describe("routes", () => {
  it("maps paths to pages", () => {
    expect(routeOf("/", "")).toBe("home");
    expect(routeOf("/map", "")).toBe("map");
    expect(routeOf("/method", "")).toBe("method");
    expect(routeOf("/about/", "")).toBe("about");
    expect(routeOf("/report", "")).toBe("report");
    expect(routeOf("/lsh/method", "/lsh")).toBe("method");
    expect(routeOf("/nope", "")).toBe("home");
  });
});
