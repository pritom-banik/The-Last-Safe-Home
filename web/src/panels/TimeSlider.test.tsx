import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import "../i18n";
import { useApp } from "../store";
import TimeSlider from "./TimeSlider";

const DATES = ["2026-06-17", "2026-06-29", "2026-07-11"];

describe("TimeSlider", () => {
  beforeEach(() => useApp.setState({ date: "2026-07-11" }));
  afterEach(cleanup);

  it("shows the selected date and steps with arrow keys", () => {
    render(<TimeSlider dates={DATES} gaps={[["2026-06-20", "2026-06-25"]]} />);
    const label = screen.getByTestId("slider-date");
    expect(label.textContent).toBe("11 Jul 2026");
    const slider = screen.getByRole("slider");
    fireEvent.keyDown(slider, { key: "ArrowLeft" });
    expect(useApp.getState().date).toBe("2026-06-29");
    fireEvent.keyDown(slider, { key: "Home" });
    expect(useApp.getState().date).toBe("2026-06-17");
    fireEvent.keyDown(slider, { key: "ArrowLeft" }); // clamps at the first pass
    expect(useApp.getState().date).toBe("2026-06-17");
    expect(screen.getAllByText("No data (instrument gap)").length).toBeGreaterThan(0);
  });

  it("labels Bangla dates with Bangla digits", async () => {
    const { default: i18n } = await import("../i18n");
    await act(() => i18n.changeLanguage("bn"));
    render(<TimeSlider dates={DATES} gaps={[]} />);
    expect(screen.getByTestId("slider-date").textContent).toContain("২০২৬");
    await act(() => i18n.changeLanguage("en"));
  });
});
