const usd = (value: number, cents: boolean) =>
  value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  });

export const formatUsd = (value: number, options: { cents?: boolean } = {}) => usd(value, !!options.cents);

/** Always carries an explicit sign, so direction never depends on colour. */
export const formatSignedUsd = (value: number) => `${value >= 0 ? '+' : '-'}${usd(Math.abs(value), true)}`;

export const formatPct = (value: number) => `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;

/**
 * Backend ratios arrive as decimal strings, e.g. "0.005" → "0.5%".
 *
 * Policy ceilings keep two decimals because 0.75% and 0.8% are different
 * limits; shares of a portfolio round to one, where more precision is noise.
 */
export const formatRatioPct = (value: number | string, maximumFractionDigits = 2) =>
  `${(Number(value) * 100).toLocaleString('en-US', { maximumFractionDigits })}%`;

/** A share of the portfolio. One decimal — the extra digit means nothing here. */
export const formatShare = (value: number) => formatRatioPct(value, 1);

/** A signed ratio as a percentage, e.g. 0.039 → "+3.9%". */
export const formatSignedRatioPct = (value: number) =>
  `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value * 100).toFixed(1)}%`;

const UNITS = [
  { threshold: 1e12, suffix: 'T' },
  { threshold: 1e9, suffix: 'B' },
  { threshold: 1e6, suffix: 'M' },
  { threshold: 1e3, suffix: 'K' },
] as const;

/**
 * Large turnover figures, e.g. 1_240_000_000 → "$1.2B".
 *
 * Written out rather than using `Intl` compact notation, which Hermes does not
 * implement — it silently falls back to the full number and turns a table
 * column into a wrapped paragraph.
 */
export function formatCompactUsd(value: number): string {
  const sign = value < 0 ? '-' : '';
  const magnitude = Math.abs(value);
  const unit = UNITS.find((candidate) => magnitude >= candidate.threshold);
  if (!unit) return `${sign}${usd(magnitude, false)}`;

  const scaled = magnitude / unit.threshold;
  // One decimal below 100, none above — "1.2B" is useful, "936.4M" is not.
  const text = scaled >= 100 ? Math.round(scaled).toString() : scaled.toFixed(1).replace(/\.0$/, '');
  return `${sign}$${text}${unit.suffix}`;
}

/** Clock time for a timestamp, in the device's locale and zone. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date);
}

export function formatRelativeTime(timestamp: number, now = Date.now()): string {
  const minutes = Math.max(0, Math.round((now - timestamp) / 60_000));
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** Relative time for an ISO timestamp, tolerating a missing or invalid value. */
export function formatRelativeIso(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return 'never';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return 'never';
  return formatRelativeTime(date.getTime(), now);
}
