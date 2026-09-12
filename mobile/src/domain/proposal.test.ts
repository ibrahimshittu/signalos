import { describe, expect, it } from '@jest/globals';
import {
  baseSymbol,
  isAwaitingDecision,
  proposalPhase,
  evidenceState,
  expiryState,
  portfolioEffect,
  quoteSymbol,
  rewardRisk,
  statusPresentation,
  strategyLabel,
} from './proposal';
import type { PortfolioSummary, TradeProposal } from './studio';

const NOW = new Date(Date.UTC(2026, 7, 14, 12, 0));

function proposal(overrides: Partial<TradeProposal> = {}): TradeProposal {
  return {
    id: 'p1',
    user_id: 'u1',
    connection_id: 'c1',
    environment: 'mainnet',
    strategy_id: 'london-opening-retest',
    strategy_version: '1.0.0',
    strategy_family: 'session_opening',
    category: 'linear',
    symbol: 'BTCUSDT',
    side: 'buy',
    order_type: 'limit',
    quantity: '0.018',
    limit_price: '68000',
    stop_loss: '67000',
    take_profit: '71000',
    leverage: '1',
    estimated_fees: '3.80',
    estimated_funding: '0.42',
    estimated_slippage: '2.10',
    estimated_max_loss: '124.80',
    market_price: '68100',
    market_observed_at: NOW.toISOString(),
    expires_at: new Date(NOW.getTime() + 20 * 60_000).toISOString(),
    thesis: 't',
    opposing_case: 'o',
    why_it_fits: 'f',
    why_reject: 'r',
    gate_report: { passed: true, failures: [] },
    status: 'available',
    proposal_hash: 'a'.repeat(64),
    created_at: NOW.toISOString(),
    updated_at: NOW.toISOString(),
    ...overrides,
  };
}

describe('reward and risk', () => {
  it('uses the limit price when the plan sets one', () => {
    expect(rewardRisk(proposal())).toBeCloseTo(3);
  });

  it('falls back to the market price for a market order', () => {
    expect(rewardRisk(proposal({ limit_price: null }))).toBeCloseTo(2.636, 3);
  });

  it('returns null rather than dividing by a zero stop distance', () => {
    expect(rewardRisk(proposal({ stop_loss: '68000' }))).toBeNull();
  });
});

describe('portfolio effect', () => {
  const summary = {
    total_equity: '12480',
    invested_value: '0',
    available_balance: '0',
  } as PortfolioSummary;

  it('expresses the maximum loss as a share of equity', () => {
    expect(portfolioEffect(proposal(), summary)).toBeCloseTo(0.01);
  });

  it('returns null with no connected portfolio', () => {
    expect(portfolioEffect(proposal(), null)).toBeNull();
    expect(portfolioEffect(proposal(), { ...summary, total_equity: '0' })).toBeNull();
  });
});

describe('expiry', () => {
  it('states remaining validity in minutes', () => {
    expect(expiryState(proposal(), NOW)).toEqual({
      state: 'open',
      minutes: 20,
      label: 'Terms valid 20m',
    });
  });

  it('switches to closing only inside the last five minutes', () => {
    const soon = proposal({ expires_at: new Date(NOW.getTime() + 4 * 60_000).toISOString() });
    expect(expiryState(soon, NOW).state).toBe('closing');
  });

  it('reports expiry once the terms have lapsed', () => {
    const past = proposal({ expires_at: new Date(NOW.getTime() - 60_000).toISOString() });
    expect(expiryState(past, NOW)).toEqual({
      state: 'expired',
      minutes: 0,
      label: 'Terms expired',
    });
  });

  it('collapses long windows to hours', () => {
    const later = proposal({ expires_at: new Date(NOW.getTime() + 150 * 60_000).toISOString() });
    expect(expiryState(later, NOW).label).toBe('Terms valid 2h');
  });
});

describe('status presentation', () => {
  it('says plainly that nothing was sent while awaiting a decision', () => {
    const presented = statusPresentation('available');
    expect(presented.label).toBe('Awaiting your decision');
    expect(presented.meaning).toContain('Nothing has been sent');
  });

  it('never surfaces a raw snake_case status', () => {
    const presented = statusPresentation('invalidated');
    expect(presented.label).toBe('Terms changed');
    expect(presented.tone).toBe('caution');
  });
});

describe('labels', () => {
  it('splits an instrument into base and quote', () => {
    expect(baseSymbol('BTCUSDT')).toBe('BTC');
    expect(quoteSymbol('BTCUSDT')).toBe('USDT');
  });

  it('renders a strategy family as words', () => {
    expect(strategyLabel('session_opening')).toBe('Session opening');
  });
});

describe('evidence', () => {
  it('confirms when every deterministic gate passed', () => {
    expect(evidenceState(proposal()).tone).toBe('positive');
  });

  it('counts and names failed gates', () => {
    const flagged = evidenceState(
      proposal({ gate_report: { passed: false, failures: ['liquidity', 'spread'] } }),
    );
    expect(flagged.label).toBe('2 gates flagged');
    expect(flagged.detail).toBe('liquidity, spread');
  });
});

describe('lifecycle phases', () => {
  it('recognizes backend proposal states without treating them as broker fills', () => {
    expect(isAwaitingDecision(proposal())).toBe(true);
    expect(proposalPhase(proposal())).toBe('awaiting');
    expect(proposalPhase(proposal({ status: 'submitted' }))).toBe('submitted');
    expect(proposalPhase(proposal({ status: 'archived' }))).toBe('closed');
    expect(proposalPhase(proposal({ status: 'invalidated' }))).toBe('closed');
    expect(proposalPhase(proposal({ status: 'rejected' }))).toBe('closed');
    expect(proposalPhase(proposal({ status: 'expired' }))).toBe('closed');
  });
});
