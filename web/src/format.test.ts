import { describe, expect, it } from "vitest";
import { formatDate, formatNumber, formatPercent, formatYear, isoDay } from "./format";

describe("formatNumber", () => {
  it("uses en-GB grouping and decimals", () => {
    expect(formatNumber(1234.567, "en", { decimals: 1 })).toBe("1,234.6");
    expect(formatNumber(38, "en")).toBe("38");
    expect(formatNumber(2.6, "en", { decimals: 1, signed: true })).toBe("+2.6");
    expect(formatNumber(0, "en", { signed: true })).toBe("0");
  });
  it("uses Bangla digits for bn", () => {
    expect(formatNumber(53, "bn")).toBe("৫৩");
    expect(formatNumber(0.017, "bn", { decimals: 3 })).toBe("০.০১৭");
  });
  it("shows a dash for missing values", () => {
    expect(formatNumber(null, "en")).toBe("–");
    expect(formatNumber(Number.NaN, "bn")).toBe("–");
    expect(formatNumber(Infinity, "en")).toBe("–");
  });
});

describe("formatPercent / formatYear", () => {
  it("formats fractions as whole percents", () => {
    expect(formatPercent(0.42, "en")).toBe("42%");
    expect(formatPercent(0.42, "bn")).toBe("৪২%");
    expect(formatPercent(null, "en")).toBe("–");
  });
  it("prints years without grouping", () => {
    expect(formatYear(1988, "en")).toBe("1988");
    expect(formatYear(2026, "bn")).toBe("২০২৬");
  });
});

describe("formatDate", () => {
  it("formats ISO dates as calendar dates in both languages", () => {
    expect(formatDate("2026-10-15", "en")).toBe("15 Oct 2026");
    expect(formatDate("2026-10-15", "en", "long")).toBe("15 October 2026");
    const bn = formatDate("2026-10-15", "bn");
    expect(bn).toContain("১৫");
    expect(bn).toContain("২০২৬");
    expect(bn).toContain("অক্টো");
  });
  it("does not shift the day with the timezone", () => {
    expect(formatDate("2026-06-17", "en")).toMatch(/^17 /);
  });
  it("passes through unknown strings and handles missing", () => {
    expect(formatDate(null, "en")).toBe("–");
    expect(formatDate("soon", "en")).toBe("soon");
  });
  it("counts days for slider spacing", () => {
    expect(isoDay("2026-06-29") - isoDay("2026-06-17")).toBe(12);
  });
});
