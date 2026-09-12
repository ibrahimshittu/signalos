import type { PortfolioSummary } from './studio';

export interface EquitySnapshot {
  /** Total equity at the time of capture. */
  equity: number;
  /** Epoch milliseconds of `captured_at`. */
  at: number;
}

/** Roughly a week of hourly captures. Enough for a 24-hour baseline. */
const HISTORY_LIMIT = 168;
const HOUR = 3_600_000;

/**
 * Appends a capture, keeping at most one point per hour.
 *
 * The backend exposes only the current `PortfolioSummary`, so the app retains
 * its own captures to answer "how has this changed". Nothing is invented: if
 * there is no baseline yet, `changeSince` returns null and the UI says so.
 */
export function recordEquity(
  history: EquitySnapshot[],
  snapshot: EquitySnapshot,
): EquitySnapshot[] {
  const last = history[history.length - 1];
  // Out-of-order captures are dropped before the same-hour check, otherwise a
  // late-arriving older reading would overwrite a newer one.
  if (last && snapshot.at <= last.at) return history;
  if (last && Math.floor(snapshot.at / HOUR) === Math.floor(last.at / HOUR)) {
    return [...history.slice(0, -1), snapshot];
  }
  return [...history, snapshot].slice(-HISTORY_LIMIT);
}

export function snapshotFrom(summary: PortfolioSummary): EquitySnapshot {
  return { equity: Number(summary.total_equity), at: new Date(summary.captured_at).getTime() };
}

export interface EquityChange {
  absolute: number;
  ratio: number;
  /** How far back the baseline actually reaches, in hours. */
  hours: number;
}

/**
 * Change against the oldest retained capture inside `windowHours`.
 *
 * Returns null until a baseline older than an hour exists, so the app never
 * shows a change derived from a single reading.
 */
export function changeSince(
  history: EquitySnapshot[],
  current: number,
  now: number,
  windowHours = 24,
): EquityChange | null {
  const cutoff = now - windowHours * HOUR;
  const baseline = history.find((point) => point.at >= cutoff) ?? history[0];
  if (!baseline || baseline.equity <= 0) return null;

  const hours = (now - baseline.at) / HOUR;
  if (hours < 1) return null;

  const absolute = current - baseline.equity;
  return { absolute, ratio: absolute / baseline.equity, hours };
}

/** "over 24h", "over 6h" — states the real window, never a rounded-up claim. */
export function describeWindow(change: EquityChange): string {
  const hours = Math.round(change.hours);
  return `over ${Math.max(1, hours)}h`;
}

/** Share of equity currently unavailable for new orders. */
export function exposureRatio(summary: PortfolioSummary): number | null {
  const equity = Number(summary.total_equity);
  if (!Number.isFinite(equity) || equity <= 0) return null;
  return Number(summary.invested_value) / equity;
}

/** True when the snapshot is old enough that it should be labelled stale. */
export function isStale(summary: PortfolioSummary, now: number, maxAgeMinutes = 15): boolean {
  return now - new Date(summary.captured_at).getTime() > maxAgeMinutes * 60_000;
}
