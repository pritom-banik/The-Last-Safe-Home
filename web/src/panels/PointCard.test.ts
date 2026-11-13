import { describe, expect, it } from "vitest";
import { yearsRange } from "./PointCard";

describe("yearsRange", () => {
  it("rounds and joins the range", () => {
    expect(yearsRange(8.6, 13.4, "en")).toBe("9–13");
    expect(yearsRange(2.1, 2.3, "en")).toBe("2");
  });
  it("shows 50+ for open or long upper bounds", () => {
    expect(yearsRange(30, null, "en")).toBe("30–50+");
    expect(yearsRange(30, 70, "bn")).toBe("৩০–৫০+");
  });
});
