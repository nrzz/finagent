/** Humanize notification test API responses for Settings UI. */

export type NotifyTestResult = {
  ok?: boolean;
  error?: string;
  message?: string;
  results?: Array<{
    ok?: boolean;
    channel?: string;
    error?: string;
    message?: string;
  }>;
  [key: string]: unknown;
};

export function formatNotifyTestResult(r: NotifyTestResult): string {
  const results = Array.isArray(r.results) ? r.results : [];
  const firstErr = results.find(
    (x) => x && (x.ok === false || (typeof x.error === "string" && x.error)),
  );
  if (r.ok === false || firstErr) {
    const msg =
      (typeof r.error === "string" && r.error) ||
      (typeof r.message === "string" && r.message) ||
      (firstErr && typeof firstErr.error === "string" && firstErr.error) ||
      (firstErr && typeof firstErr.message === "string" && firstErr.message) ||
      "unknown error";
    return `Test failed: ${msg}`;
  }
  return "Test sent OK";
}
