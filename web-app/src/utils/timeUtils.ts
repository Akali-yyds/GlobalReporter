export const DEFAULT_RECENT_HOURS = 24;

/** Returns the number of hours elapsed since local midnight (minimum 1). */
export function hoursSinceMidnight(): number {
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  return Math.max(1, Math.ceil((now.getTime() - midnight.getTime()) / 3_600_000));
}
