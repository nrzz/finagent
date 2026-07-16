export type TfKey = "1D" | "5D" | "1M" | "3M" | "1Y" | "1H" | "15m" | "5m";

/** Simple moving average; leading bars before `period` are null. */
export function sma(closes: number[], period: number): (number | null)[] {
  if (period <= 0) return closes.map(() => null);
  const out: (number | null)[] = [];
  let sum = 0;
  for (let i = 0; i < closes.length; i++) {
    sum += closes[i];
    if (i >= period) sum -= closes[i - period];
    if (i >= period - 1) out.push(sum / period);
    else out.push(null);
  }
  return out;
}

export function tfToQuery(tf: TfKey): { period: string; interval: string } {
  switch (tf) {
    case "1D":
      return { period: "1d", interval: "5m" };
    case "5D":
      return { period: "5d", interval: "15m" };
    case "1M":
      return { period: "1mo", interval: "1d" };
    case "3M":
      return { period: "3mo", interval: "1d" };
    case "1Y":
      return { period: "1y", interval: "1d" };
    case "1H":
      return { period: "5d", interval: "1h" };
    case "15m":
      return { period: "5d", interval: "15m" };
    case "5m":
      return { period: "1d", interval: "5m" };
    default:
      return { period: "1mo", interval: "1d" };
  }
}

export function isDailyInterval(interval: string): boolean {
  return interval === "1d" || interval === "1wk" || interval === "1mo";
}
