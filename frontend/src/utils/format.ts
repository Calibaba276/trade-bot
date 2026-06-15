// Shared display formatters — see design guide §14 (WAT timestamps, short IDs).

/** Format an epoch-ms timestamp as HH:MM:SS in WAT (Africa/Lagos, UTC+1). */
export function fmtTimeWAT(ms: number): string {
  return new Date(ms).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Africa/Lagos",
  });
}

/** Format an epoch-ms timestamp as "Jan 23 10:25" in WAT. */
export function fmtDateTimeWAT(ms: number): string {
  return new Date(ms).toLocaleString("en-GB", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Africa/Lagos",
  });
}

/** Never show raw UUIDs — display the last 4 chars uppercased, prefixed with #. */
export function shortId(id?: string | null): string {
  if (!id) return "#----";
  return "#" + id.replace(/[^a-zA-Z0-9]/g, "").slice(-4).toUpperCase();
}

/** Price with pair-aware decimals (JPY pairs use 3 dp, others 5 dp). */
export function fmtPrice(price: number, pair: string): string {
  return price.toFixed(pair.includes("JPY") ? 3 : 5);
}

/** Signed dollar amount, e.g. +$482 / -$120. */
export function fmtMoney(n: number, decimals = 0): string {
  const sign = n >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(n).toFixed(decimals)}`;
}
