import { describe, expect, it } from "vitest";
import { decodeUrlState, encodeUrlState } from "./urlState";

describe("URL state", () => {
  it("round-trips a full view", () => {
    const s = {
      site: "manpura",
      lat: 22.28,
      lon: 90.97,
      z: 11.5,
      layers: ["score", "banklines"],
      date: "2026-09-14",
      lang: "bn" as const,
      mode: "compare" as const,
      pt: [90.98, 22.3] as [number, number],
    };
    const qs = encodeUrlState(s);
    expect(qs).toBe(
      "site=manpura&lat=22.28000&lon=90.97000&z=11.5&layers=score,banklines&date=2026-09-14&lang=bn&mode=compare&pt=90.98000,22.30000",
    );
    expect(decodeUrlState(`?${qs}`)).toEqual(s);
  });

  it("keeps an explicitly empty layer list", () => {
    expect(decodeUrlState("?layers=").layers).toEqual([]);
    expect(encodeUrlState({ layers: [] })).toBe("layers=");
  });

  it("drops invalid or hostile values", () => {
    const u = decodeUrlState(
      "?site=../etc&lat=abc&lon=90&z=99&layers=score,<script>,water&date=2026-9-1&lang=fr&mode=x&pt=200,10",
    );
    expect(u).toEqual({ layers: ["score", "water"] });
  });

  it("needs both lat and lon", () => {
    expect(decodeUrlState("?lat=22.3").lat).toBeUndefined();
    expect(decodeUrlState("?lat=22.3&lon=90.9")).toEqual({ lat: 22.3, lon: 90.9 });
  });
});
