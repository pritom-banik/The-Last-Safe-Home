import { describe, expect, it } from "vitest";
import { legacyMapPath, routeOf } from "./router";

describe("routeOf", () => {
  it("maps paths to pages", () => {
    expect(routeOf("/", "")).toBe("home");
    expect(routeOf("/index.html", "")).toBe("home");
    expect(routeOf("/map", "")).toBe("map");
    expect(routeOf("/map/", "")).toBe("map");
    expect(routeOf("/method", "")).toBe("method");
    expect(routeOf("/about", "")).toBe("about");
    expect(routeOf("/report", "")).toBe("report");
    expect(routeOf("/nope", "")).toBe("home");
  });
  it("strips a sub-path base", () => {
    expect(routeOf("/nasa/", "/nasa")).toBe("home");
    expect(routeOf("/nasa/map", "/nasa")).toBe("map");
  });
});

describe("legacyMapPath", () => {
  it("sends old root map links to /map", () => {
    expect(legacyMapPath("/", "?site=demo&lat=22.6&lon=90.6", "")).toBe("/map?site=demo&lat=22.6&lon=90.6");
    expect(legacyMapPath("/nasa/", "?pt=1,2", "/nasa")).toBe("/nasa/map?pt=1,2");
  });
  it("leaves the home page and other pages alone", () => {
    expect(legacyMapPath("/", "", "")).toBeNull();
    expect(legacyMapPath("/", "?lang=bn", "")).toBeNull();
    expect(legacyMapPath("/map", "?site=demo", "")).toBeNull();
    expect(legacyMapPath("/method", "?site=demo", "")).toBeNull();
  });
});
