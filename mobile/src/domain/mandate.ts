import type { AdaptiveRiskMandate, InvestmentProfileInput } from './studio';

/** Plain-language name for each posture the policy can produce. */
export const postureLabels: Record<AdaptiveRiskMandate['risk_posture'], string> = {
  capital_protective: 'Capital protective',
  measured: 'Measured',
  selective_growth: 'Selective growth',
};

/**
 * Why the policy landed where it did.
 *
 * The user did not choose these ceilings, so the app has to be able to explain
 * every one of them in their own terms.
 */
const reasonLabels: Record<string, string> = {
  capital_preservation_goal: 'You chose to protect capital first.',
  high_liquidity_need: 'You may need this money at short notice.',
  new_investor: 'You are early in your investing experience.',
  new_trader: 'You have not actively traded before.',
  drawdown_uncertainty: 'You would rather step back than sit through a loss.',
  advanced_market_experience: 'You have managed positions through varied conditions.',
  bounded_derivatives_experience: 'Your derivatives experience allows a bounded allowance.',
  balanced_suitability_inputs: 'Your answers sit in the middle of the range.',
  derivatives_experience_verified: 'You have traded leveraged products before.',
  spot_first: 'SignalOS starts you spot-first.',
};

export function mandateReason(code: string): string {
  return reasonLabels[code] ?? code.replaceAll('_', ' ');
}

const derivatives = new Set(['futures', 'options']);

export function deriveAdaptiveMandate(profile: InvestmentProfileInput): AdaptiveRiskMandate {
  const reasons: string[] = [];
  let protective = false;
  if (profile.goals.includes('capital_preservation')) {
    protective = true;
    reasons.push('capital_preservation_goal');
  }
  if (profile.liquidity_need === 'high') {
    protective = true;
    reasons.push('high_liquidity_need');
  }
  if (profile.investing_experience === 'none') {
    protective = true;
    reasons.push('new_investor');
  }
  if (profile.trading_experience === 'none') {
    protective = true;
    reasons.push('new_trader');
  }
  if (profile.drawdown_response === 'exit' || profile.drawdown_response === 'unsure') {
    protective = true;
    reasons.push('drawdown_uncertainty');
  }

  const hasDerivativesExperience = profile.products_traded.some((item) => derivatives.has(item));
  const derivativesEligible = hasDerivativesExperience
    && (profile.trading_experience === 'intermediate' || profile.trading_experience === 'advanced');

  if (protective) {
    return {
      risk_posture: 'capital_protective',
      max_loss_per_trade_pct: '0.005',
      max_portfolio_drawdown_pct: '0.06',
      max_leverage: '1',
      derivatives_eligible: false,
      reasons,
      policy_version: 'adaptive-mandate-2.0.0',
    };
  }

  const selectiveGrowth = profile.goals.includes('capital_growth')
    && profile.liquidity_need === 'low'
    && profile.investing_experience === 'advanced'
    && profile.trading_experience === 'advanced'
    && (profile.decision_frequency === 'weekly' || profile.decision_frequency === 'daily')
    && derivativesEligible;
  if (selectiveGrowth) {
    return {
      risk_posture: 'selective_growth',
      max_loss_per_trade_pct: '0.01',
      max_portfolio_drawdown_pct: '0.12',
      max_leverage: '20',
      derivatives_eligible: true,
      reasons: ['advanced_market_experience', 'bounded_derivatives_experience'],
      policy_version: 'adaptive-mandate-2.0.0',
    };
  }

  return {
    risk_posture: 'measured',
    max_loss_per_trade_pct: '0.0075',
    max_portfolio_drawdown_pct: '0.08',
    max_leverage: derivativesEligible ? '1.5' : '1',
    derivatives_eligible: derivativesEligible,
    reasons: ['balanced_suitability_inputs', derivativesEligible ? 'derivatives_experience_verified' : 'spot_first'],
    policy_version: 'adaptive-mandate-2.0.0',
  };
}
