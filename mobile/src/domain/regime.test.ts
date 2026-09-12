import { describe, expect, it } from '@jest/globals';
import { deriveMarketRegime } from './regime';
import type { MarketCandidate, MarketScan } from './studio';

const OBSERVED = '2026-08-14T12:00:00.000Z';

function candidate(symbol: string, change: number): MarketCandidate {
  return {
    category: 'linear',
    symbol,
    activity_score: '0.8',
    turnover_24h: '1000000',
    price_change_24h: change.toFixed(4),
    spread_bps: '1.80',
    observed_at: OBSERVED,
  };
}

function scan(changes: number[]): MarketScan {
  const universe = changes.map((change, index) => candidate(`SYM${index}USDT`, change));
  return {
    id: 'scan-1',
    environment: 'mainnet',
    source_count: 426,
    observed_at: OBSERVED,
    created_at: OBSERVED,
    result: { hot_universe: universe, agent_shortlist: universe.slice(0, 3) },
  };
}

describe('market regime', () => {
  it('returns nothing when no scan has landed', () => {
    expect(deriveMarketRegime(null)).toBeNull();
    expect(deriveMarketRegime(scan([]))).toBeNull();
  });

  it('calls a broad advance when most of the universe is up', () => {
    const regime = deriveMarketRegime(scan([0.03, 0.02, 0.01, 0.04, -0.01]))!;
    expect(regime.label).toBe('broad_advance');
    expect(regime.advancing).toBe(4);
    expect(regime.declining).toBe(1);
  });

  it('calls a broad decline when most of the universe is down', () => {
    expect(deriveMarketRegime(scan([-0.03, -0.02, -0.01, -0.04, 0.01]))!.label).toBe('broad_decline');
  });

  it('calls mixed breadth in between', () => {
    expect(deriveMarketRegime(scan([0.02, 0.01, -0.02, -0.01]))!.label).toBe('mixed');
  });

  it('refuses to characterise a universe that is too small', () => {
    const regime = deriveMarketRegime(scan([0.02, 0.03]))!;
    expect(regime.label).toBe('unclear');
    expect(regime.summary).toContain('Too few');
  });

  it('reports median absolute movement rather than an average skewed by outliers', () => {
    const regime = deriveMarketRegime(scan([0.01, 0.01, 0.01, 0.5, -0.01]))!;
    expect(regime.dispersion).toBeCloseTo(0.01);
    expect(regime.summary).toContain('1.0%');
  });

  it('carries the observation time through so freshness can be shown', () => {
    expect(deriveMarketRegime(scan([0.01, 0.02, 0.03]))!.observedAt).toBe(OBSERVED);
  });
});
