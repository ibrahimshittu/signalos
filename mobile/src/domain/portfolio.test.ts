import { describe, expect, it } from '@jest/globals';
import {
  changeSince,
  describeWindow,
  exposureRatio,
  isStale,
  recordEquity,
  snapshotFrom,
} from './portfolio';
import type { PortfolioSummary } from './studio';

const HOUR = 3_600_000;
const NOW = Date.UTC(2026, 7, 14, 12, 0, 0);

function summary(overrides: Partial<PortfolioSummary> = {}): PortfolioSummary {
  return {
    connection_id: 'c1',
    provider_id: 'bybit',
    environment: 'mainnet',
    account_type: 'UNIFIED',
    total_equity: '12480.55',
    available_balance: '8200.00',
    invested_value: '4280.55',
    balances: [],
    captured_at: new Date(NOW).toISOString(),
    ...overrides,
  };
}

describe('equity history', () => {
  it('keeps at most one capture per hour by replacing the most recent', () => {
    const history = recordEquity([{ equity: 100, at: NOW - HOUR }], {
      equity: 101,
      at: NOW - HOUR / 2,
    });
    expect(history).toEqual([{ equity: 101, at: NOW - HOUR / 2 }]);
  });

  it('appends once an hour has passed', () => {
    const history = recordEquity([{ equity: 100, at: NOW - 2 * HOUR }], { equity: 110, at: NOW });
    expect(history).toHaveLength(2);
  });

  it('ignores captures that are older than what is already stored', () => {
    const existing = [{ equity: 100, at: NOW }];
    expect(recordEquity(existing, { equity: 90, at: NOW - 5 * HOUR })).toBe(existing);
  });

  it('retains hourly history during continuous five-minute refreshes', () => {
    let history: { equity: number; at: number }[] = [];
    for (let minute = 0; minute <= 120; minute += 5) {
      history = recordEquity(history, { equity: 100 + minute, at: NOW + minute * 60_000 });
    }
    expect(history).toHaveLength(3);
    expect(changeSince(history, 220, NOW + 2 * HOUR)).not.toBeNull();
  });

  it('reads a snapshot straight off a portfolio summary', () => {
    expect(snapshotFrom(summary())).toEqual({ equity: 12480.55, at: NOW });
  });
});

describe('change since a baseline', () => {
  it('reports nothing until a baseline at least an hour old exists', () => {
    expect(changeSince([], 12480, NOW)).toBeNull();
    expect(changeSince([{ equity: 12000, at: NOW - 30 * 60_000 }], 12480, NOW)).toBeNull();
  });

  it('measures against the oldest capture inside the window', () => {
    const history = [
      { equity: 10000, at: NOW - 48 * HOUR },
      { equity: 12000, at: NOW - 20 * HOUR },
      { equity: 12300, at: NOW - 2 * HOUR },
    ];
    const change = changeSince(history, 12480, NOW);
    expect(change).not.toBeNull();
    expect(change!.absolute).toBeCloseTo(480);
    expect(change!.ratio).toBeCloseTo(0.04);
    expect(describeWindow(change!)).toBe('over 20h');
  });

  it('states the real window when history is shorter than requested', () => {
    const change = changeSince([{ equity: 12000, at: NOW - 6 * HOUR }], 12480, NOW);
    expect(describeWindow(change!)).toBe('over 6h');
  });

  it('does not label a two-day-old baseline as a 24-hour change', () => {
    const change = changeSince([{ equity: 100, at: NOW - 48 * HOUR }], 110, NOW);
    expect(describeWindow(change!)).toBe('over 48h');
  });

  it('handles a decline without losing the sign', () => {
    const change = changeSince([{ equity: 13000, at: NOW - 5 * HOUR }], 12480, NOW);
    expect(change!.absolute).toBeLessThan(0);
    expect(change!.ratio).toBeLessThan(0);
  });
});

describe('exposure and freshness', () => {
  it('expresses funds in use as a share of equity', () => {
    expect(exposureRatio(summary())).toBeCloseTo(0.343, 3);
  });

  it('refuses to divide by a zero or missing equity', () => {
    expect(exposureRatio(summary({ total_equity: '0' }))).toBeNull();
  });

  it('marks a snapshot stale once it passes the age limit', () => {
    expect(isStale(summary(), NOW)).toBe(false);
    expect(isStale(summary(), NOW + 16 * 60_000)).toBe(true);
  });
});
