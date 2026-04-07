export const DEFAULT_RECENT_HOURS = 24;
export const NEWS_FILTER_LOOKBACK_HOURS = 72;
export const BEIJING_UTC_OFFSET_HOURS = 8;
const HOUR_MS = 3_600_000;
const DAY_MS = 24 * HOUR_MS;

export type NewsTimeRange = 'today' | 'yesterday' | '3days';

function hasExplicitTimezone(value: string): boolean {
  return /(?:Z|[+\-]\d{2}:\d{2})$/i.test(value);
}

/**
 * Parse API datetimes consistently.
 * Backend currently returns naive UTC timestamps, so we coerce them to UTC before
 * converting to the local timezone in the browser.
 */
export function parseApiDate(value: string): Date {
  const normalized = hasExplicitTimezone(value) ? value : `${value}Z`;
  return new Date(normalized);
}

function getBeijingDayIndex(date: Date): number {
  return Math.floor((date.getTime() + (BEIJING_UTC_OFFSET_HOURS * HOUR_MS)) / DAY_MS);
}

/** Returns the number of hours elapsed since local midnight (minimum 1). */
export function hoursSinceMidnight(): number {
  const now = new Date();
  const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  return Math.max(1, Math.ceil((now.getTime() - midnight.getTime()) / 3_600_000));
}

/** Returns the number of hours elapsed since Beijing midnight (minimum 1). */
export function hoursSinceBeijingMidnight(now: Date = new Date()): number {
  const shiftedMs = now.getTime() + (BEIJING_UTC_OFFSET_HOURS * HOUR_MS);
  const elapsedMs = ((shiftedMs % DAY_MS) + DAY_MS) % DAY_MS;
  return Math.max(1, Math.ceil(elapsedMs / HOUR_MS));
}

export function isEventInTimeRange(
  isoString: string,
  timeRange: NewsTimeRange,
  now: Date = new Date(),
): boolean {
  const eventDate = parseApiDate(isoString);
  if (Number.isNaN(eventDate.getTime())) {
    return false;
  }
  const currentBeijingDay = getBeijingDayIndex(now);
  const eventBeijingDay = getBeijingDayIndex(eventDate);

  if (timeRange === 'today') {
    return eventBeijingDay === currentBeijingDay;
  }
  if (timeRange === 'yesterday') {
    return eventBeijingDay === currentBeijingDay - 1;
  }
  return eventBeijingDay >= currentBeijingDay - 2 && eventBeijingDay <= currentBeijingDay;
}
