// Forex market session helpers — single source of truth for open/closed state.
// Market runs Sunday 22:00 UTC through Friday 22:00 UTC.

/** Whether the forex market is currently open. */
export function isMarketOpen(d: Date = new Date()): boolean {
  const day = d.getUTCDay(); // 0=Sun, 6=Sat
  const hour = d.getUTCHours();
  if (day === 6) return false; // all Saturday
  if (day === 5 && hour >= 22) return false; // Friday after close
  if (day === 0 && hour < 22) return false; // Sunday before open
  return true;
}

/** The next moment the market opens (Sunday 22:00 UTC). */
export function getNextMarketOpen(from: Date = new Date()): Date {
  const day = from.getUTCDay();
  const hour = from.getUTCHours();

  const next = new Date(from);
  next.setUTCMinutes(0, 0, 0);
  next.setUTCHours(22);

  if (day === 0 && hour < 22) return next; // opens later today

  const daysUntilSunday = (7 - day) % 7 || 7;
  next.setUTCDate(from.getUTCDate() + daysUntilSunday);
  return next;
}
