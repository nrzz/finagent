import { describe, expect, it } from "vitest";
import { sma, tfToQuery } from "./chartMath";

describe("sma", () => {
  it("returns nulls until period is filled", () => {
    expect(sma([1, 2, 3, 4], 3)).toEqual([null, null, 2, 3]);
  });
});

describe("tfToQuery", () => {
  it("maps timeframes to period/interval", () => {
    expect(tfToQuery("1D")).toEqual({ period: "1d", interval: "5m" });
    expect(tfToQuery("5D")).toEqual({ period: "5d", interval: "15m" });
    expect(tfToQuery("1M")).toEqual({ period: "1mo", interval: "1d" });
    expect(tfToQuery("5m")).toEqual({ period: "1d", interval: "5m" });
  });
});
