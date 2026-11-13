import { describe, expect, it } from "vitest";
import { apiBase } from "./config";

describe("apiBase", () => {
  it("defaults to localhost", () => {
    expect(apiBase(undefined)).toBe("http://localhost:8000/api/v1");
    expect(apiBase("  ")).toBe("http://localhost:8000/api/v1");
  });
  it("appends /api/v1 once", () => {
    expect(apiBase("https://api.example.org/")).toBe("https://api.example.org/api/v1");
    expect(apiBase("https://api.example.org/api/v1/")).toBe("https://api.example.org/api/v1");
  });
});
