import { describe, expect, it } from "vitest";
import { formatNotifyTestResult } from "./notify";

describe("formatNotifyTestResult", () => {
  it("formats success", () => {
    expect(formatNotifyTestResult({ ok: true })).toBe("Test sent OK");
  });

  it("formats failure with top-level error", () => {
    expect(formatNotifyTestResult({ ok: false, error: "SMTP refused" })).toBe(
      "Test failed: SMTP refused",
    );
  });

  it("parses first error from results array", () => {
    expect(
      formatNotifyTestResult({
        ok: false,
        results: [
          { ok: true, channel: "webhook" },
          { ok: false, channel: "discord", error: "404" },
        ],
      }),
    ).toBe("Test failed: 404");
  });

  it("treats failed result as failure even if ok omitted", () => {
    expect(
      formatNotifyTestResult({
        results: [{ ok: false, error: "timeout" }],
      }),
    ).toBe("Test failed: timeout");
  });
});
