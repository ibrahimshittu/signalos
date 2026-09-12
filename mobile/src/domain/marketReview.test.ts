import { describe, expect, it } from '@jest/globals';
import { explainMarketReview, proposalEmptyState } from './marketReview';

describe('explainMarketReview', () => {
  it('explains an unavailable live strategy catalog without calling it a rejected trade', () => {
    const explanation = explainMarketReview(
      {
        category: 'linear',
        symbol: 'COWUSDT',
        rank: 1,
        status: 'no_approved_strategy',
        reason: 'No live strategy is available for trade analysis.',
        strategy_id: null,
      },
      0,
    );

    expect(explanation.stage).toBe('Strategy validation pending');
    expect(explanation.title).toBe('Trade analysis unavailable');
    expect(explanation.reason).toContain('passed the market screen');
    expect(explanation.note).toContain('entry, stop, target, size, or leverage');
    expect(explanation.steps).toEqual([
      expect.objectContaining({ label: 'Market screen', state: 'passed' }),
      expect.objectContaining({ label: 'Strategy review', state: 'unavailable' }),
      expect.objectContaining({ label: 'Trade and portfolio review', state: 'not_run' }),
    ]);
  });

  it('keeps a genuine strategy coverage miss distinct from an unavailable catalog', () => {
    const explanation = explainMarketReview(
      {
        category: 'linear',
        symbol: 'PORTALUSDT',
        rank: 1,
        status: 'no_strategy_match',
        reason: 'No live strategy covers this market.',
        strategy_id: null,
      },
      2,
    );

    expect(explanation.stage).toBe('No strategy match');
    expect(explanation.title).toBe('No strategy fit');
    expect(explanation.reason).toContain('does not cover this market');
    expect(explanation.steps).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: 'Strategy coverage', state: 'stopped' }),
      ]),
    );
  });

  it('keeps an AI no-trade decision distinct from a deterministic rejection', () => {
    const explanation = explainMarketReview(
      {
        category: 'spot',
        symbol: 'BTCUSDT',
        rank: 2,
        status: 'ai_no_trade',
        reason: 'The opposing evidence outweighed the setup.',
        strategy_id: 'managed-trend-filter',
      },
      2,
    );

    expect(explanation.stage).toBe('Stopped at analyst review');
    expect(explanation.steps).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ label: 'Deterministic setup', state: 'passed' }),
        expect.objectContaining({ label: 'Analyst review', state: 'stopped' }),
      ]),
    );
    expect(explanation.reason).toBe('The opposing evidence outweighed the setup.');
  });

  it('does not imply that another scan can create a proposal when no strategy is live', () => {
    expect(proposalEmptyState({ approved_strategies: 0 })).toEqual({
      actionTitle: 'Refresh market review',
      body: 'Strategies are still being validated, so market reviews cannot create proposals yet.',
      title: 'No proposals yet',
    });
  });
});
