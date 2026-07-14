import { describe, expect, it } from "vitest";
import { formatNumber } from "./utils";

describe("formatNumber", () => {
  it("formats indian", () => {
    expect(formatNumber(1234567.8, "indian")).toContain("12,34,567");
  });
});