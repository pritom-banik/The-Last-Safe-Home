import { describe, expect, it } from "vitest";
import { classColour, scoreClass } from "./score";

describe("scoreClass", () => {
  it("maps class boundaries as in SPEC §8", () => {
    expect(scoreClass(0)).toBe("low");
    expect(scoreClass(24)).toBe("low");
    expect(scoreClass(25)).toBe("moderate");
    expect(scoreClass(49)).toBe("moderate");
    expect(scoreClass(50)).toBe("high");
    expect(scoreClass(53)).toBe("high");
    expect(scoreClass(74)).toBe("high");
    expect(scoreClass(75)).toBe("severe");
    expect(scoreClass(100)).toBe("severe");
  });
  it("returns null for no score (river pixels)", () => {
    expect(scoreClass(null)).toBeNull();
    expect(scoreClass(undefined)).toBeNull();
    expect(scoreClass(Number.NaN)).toBeNull();
  });
  it("has the spec colours", () => {
    expect(classColour("low")).toBe("#1a9850");
    expect(classColour("moderate")).toBe("#fee08b");
    expect(classColour("high")).toBe("#f46d43");
    expect(classColour("severe")).toBe("#a50026");
  });
});
