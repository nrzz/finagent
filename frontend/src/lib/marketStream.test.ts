import { describe, expect, it } from "vitest";
import { nextBackoffMs, parseSymbolsParam } from "./marketStream";

describe("parseSymbolsParam", () => {
  it("splits and trims comma-separated symbols", () => {
    expect(parseSymbolsParam("AAPL, MSFT ,  ,GOOGL")).toEqual(["AAPL", "MSFT", "GOOGL"]);
  });

  it("dedupes while preserving order", () => {
    expect(parseSymbolsParam("AAPL,AAPL, MSFT")).toEqual(["AAPL", "MSFT"]);
  });

  it("returns empty for blank input", () => {
    expect(parseSymbolsParam("  ,  ")).toEqual([]);
  });
});

describe("nextBackoffMs", () => {
  it("uses 1s, 2s, then 5s max", () => {
    expect(nextBackoffMs(0)).toBe(1000);
    expect(nextBackoffMs(1)).toBe(2000);
    expect(nextBackoffMs(2)).toBe(5000);
    expect(nextBackoffMs(9)).toBe(5000);
  });
});
