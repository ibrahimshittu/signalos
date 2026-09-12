import type { MarketReview, MarketReviewCandidate } from './studio';

export type ReviewStepState = 'passed' | 'stopped' | 'unavailable' | 'not_run';

export interface ReviewStep {
  label: string;
  detail: string;
  state: ReviewStepState;
}

export interface MarketReviewExplanation {
  stage: string;
  title: string;
  reason: string;
  note?: string;
  next: string;
  steps: ReviewStep[];
}

const notRun = (label: string, detail: string): ReviewStep => ({
  label,
  detail,
  state: 'not_run',
});

const passed = (label: string, detail: string): ReviewStep => ({
  label,
  detail,
  state: 'passed',
});

const stopped = (label: string, detail: string): ReviewStep => ({
  label,
  detail,
  state: 'stopped',
});

const unavailable = (label: string, detail: string): ReviewStep => ({
  label,
  detail,
  state: 'unavailable',
});

const shortlist = (candidate: MarketReviewCandidate) =>
  passed('Market screen', `Ranked #${candidate.rank} for liquidity and market activity.`);

const strategyName = (candidate: MarketReviewCandidate) =>
  candidate.strategy_id
    ? `Strategy ${candidate.strategy_id} matched this market.`
    : 'A strategy matched this market.';

const noStrategyMatch = (candidate: MarketReviewCandidate): MarketReviewExplanation => ({
  stage: 'No strategy match',
  title: 'No strategy fit',
  reason: 'The live strategy library does not cover this market.',
  note: 'No entry, stop, target, size, or leverage was calculated.',
  next: 'A later review can reconsider it if the strategy library expands.',
  steps: [
    shortlist(candidate),
    stopped('Strategy coverage', 'The live strategies do not support this market.'),
    notRun('Trade and portfolio review', 'No trade setup or user-specific sizing was run.'),
  ],
});

export function proposalEmptyState(review?: Pick<MarketReview, 'approved_strategies'>): {
  actionTitle: string;
  body: string;
  title: string;
} {
  if (review?.approved_strategies === 0) {
    return {
      actionTitle: 'Refresh market review',
      body: 'Strategies are still being validated, so market reviews cannot create proposals yet.',
      title: 'No proposals yet',
    };
  }
  return {
    actionTitle: 'Review markets',
    body: 'No current setup has cleared every strategy and risk check.',
    title: 'No proposals yet',
  };
}

/**
 * Converts the typed pipeline stop into plain-language, stage-accurate copy.
 * It never claims that a skipped check passed and never turns a shortlist into
 * a recommendation.
 */
export function explainMarketReview(
  candidate: MarketReviewCandidate,
  approvedStrategyCount: number,
): MarketReviewExplanation {
  switch (candidate.status) {
    case 'model_unavailable':
      return {
        stage: 'Analysis unavailable',
        title: 'Review unavailable',
        reason: candidate.reason,
        note: 'This is a system limitation, not a negative view of the market.',
        next: 'SignalOS will retry when the analysis service is available.',
        steps: [
          shortlist(candidate),
          stopped('Analysis service', 'The model-backed review was unavailable.'),
          notRun('Trade analysis', 'No thesis or opposing case was produced.'),
          notRun('Portfolio fit', 'Your portfolio was not evaluated for this candidate.'),
        ],
      };
    case 'market_data_unavailable':
      return {
        stage: 'Data check incomplete',
        title: 'Insufficient market data',
        reason: candidate.reason,
        note: 'SignalOS does not form trade plans from incomplete or stale observations.',
        next: 'The candidate can be reconsidered after a later scan has the required fresh data.',
        steps: [
          shortlist(candidate),
          stopped('Market data', 'Required instrument or ticker details were unavailable.'),
          notRun('Trade analysis', 'No setup was evaluated.'),
          notRun('Portfolio fit', 'Your portfolio was not evaluated for this candidate.'),
        ],
      };
    case 'no_approved_strategy':
      if (approvedStrategyCount > 0) return noStrategyMatch(candidate);
      return {
        stage: 'Strategy validation pending',
        title: 'Trade analysis unavailable',
        reason:
          'This market passed the market screen, but no live strategy is available to evaluate it yet.',
        note: 'No entry, stop, target, size, or leverage was calculated.',
        next: 'Trade analysis can begin after a strategy completes validation and operator approval.',
        steps: [
          shortlist(candidate),
          unavailable('Strategy review', 'No live strategy is available for trade analysis.'),
          notRun(
            'Trade and portfolio review',
            'No setup, risk plan, or user-specific sizing was run.',
          ),
        ],
      };
    case 'no_strategy_match':
      return noStrategyMatch(candidate);
    case 'evidence_gate_rejected':
      return {
        stage: 'Evidence check incomplete',
        title: 'Strategy not cleared',
        reason: candidate.reason,
        note: 'A matched strategy cannot be used until its research and validation evidence passes governance.',
        next: 'The strategy must pass its evidence checks before this market can proceed.',
        steps: [
          shortlist(candidate),
          passed('Strategy match', strategyName(candidate)),
          stopped('Evidence gate', 'The matched strategy is not cleared for proposal use.'),
          notRun('Portfolio fit', 'Your portfolio was not exposed to an unapproved strategy.'),
        ],
      };
    case 'no_valid_signal':
      return {
        stage: 'Stopped at setup check',
        title: 'No valid setup',
        reason: candidate.reason,
        note: 'Completed candles did not satisfy the strategy’s deterministic entry rules.',
        next: 'A later review may reconsider it if price, trend, volatility, and volume form a valid setup.',
        steps: [
          shortlist(candidate),
          passed('Strategy and evidence', strategyName(candidate)),
          stopped('Deterministic setup', 'The closed-candle entry conditions were not met.'),
          notRun('Portfolio fit', 'Sizing was unnecessary because no setup existed.'),
        ],
      };
    case 'ai_no_trade':
      return {
        stage: 'Stopped at analyst review',
        title: 'No trade recommended',
        reason: candidate.reason,
        note: 'A valid deterministic setup existed, but the specialist review found the opposing case too strong or the evidence insufficient.',
        next: 'SignalOS will reassess it with fresh market context during a later deep review.',
        steps: [
          shortlist(candidate),
          passed('Strategy and evidence', strategyName(candidate)),
          passed('Deterministic setup', 'Closed candles formed a strategy-valid setup.'),
          stopped('Analyst review', candidate.reason),
          notRun('Portfolio fit', 'The global market case stopped before user-specific sizing.'),
        ],
      };
    case 'passed_market_checks':
      return {
        stage: 'Market review passed',
        title: 'Market checks passed',
        reason: candidate.reason,
        note: 'A proposal exists only if your current holdings, mandate, costs, and risk limits also pass.',
        next: 'Check Proposals for a user-specific plan with exact entry, invalidation, size, leverage, and maximum loss.',
        steps: [
          shortlist(candidate),
          passed('Strategy and evidence', strategyName(candidate)),
          passed('Deterministic setup', 'The market formed a strategy-valid setup.'),
          passed('Analyst review', 'The market case survived specialist challenge.'),
          candidate.portfolio_review
            ? (['proposed', 'already_proposed'].includes(candidate.portfolio_review.code)
                ? passed
                : stopped)('Portfolio fit', candidate.portfolio_review.reason)
            : notRun('Portfolio fit', 'No account-specific outcome was recorded for this review.'),
        ],
      };
  }
}
