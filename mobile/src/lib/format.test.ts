import { describe, expect, it } from '@jest/globals';
import {
  formatCompactUsd,
  formatPct,
  formatRatioPct,
  formatRelativeIso,
  formatRelativeTime,
  formatSignedRatioPct,
  formatSignedUsd,
  formatUsd,
} from './format';

const NOW = 1_700_000_000_000;

describe('money formatting', () => {
  it('formats whole and signed dollar amounts', () => {
    expect(formatUsd(5142.2)).toBe('$5,142');
    expect(formatUsd(5142.2, { cents: true })).toBe('$5,142.20');
    expect(formatSignedUsd(-19)).toBe('-$19.00');
    expect(formatSignedUsd(19)).toBe('+$19.00');
  });

  it('compacts large turnover figures without relying on Intl notation', () => {
    expect(formatCompactUsd(1_240_000_000)).toBe('$1.2B');
    expect(formatCompactUsd(936_000_000)).toBe('$936M');
    expect(formatCompactUsd(1_152_000_000)).toBe('$1.2B');
    expect(formatCompactUsd(4_500)).toBe('$4.5K');
    expect(formatCompactUsd(820)).toBe('$820');
    expect(formatCompactUsd(-2_300_000)).toBe('-$2.3M');
  });
});

describe('percentages', () => {
  it('shows the sign on positive percentages', () => {
    expect(formatPct(2.834)).toBe('+2.8%');
  });

  it('formats API ratios as user-facing percentages', () => {
    expect(formatRatioPct('0.005')).toBe('0.5%');
  });

  it('carries an explicit sign on a signed ratio so colour is never the only cue', () => {
    expect(formatSignedRatioPct(0.039)).toBe('+3.9%');
    expect(formatSignedRatioPct(-0.039)).toBe('−3.9%');
    expect(formatSignedRatioPct(0)).toBe('0.0%');
  });
});

describe('time', () => {
  it('formats relative time', () => {
    expect(formatRelativeTime(NOW - 120_000, NOW)).toBe('2m ago');
  });

  it('degrades to "never" for a missing or unparseable timestamp', () => {
    expect(formatRelativeIso(null, NOW)).toBe('never');
    expect(formatRelativeIso('not-a-date', NOW)).toBe('never');
  });

  it('reads an ISO timestamp as relative time', () => {
    expect(formatRelativeIso(new Date(NOW - 3 * 60_000).toISOString(), NOW)).toBe('3m ago');
  });
});
