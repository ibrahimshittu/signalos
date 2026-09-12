import { describe, expect, it } from '@jest/globals';
import type { InvestmentProfileInput } from './studio';
import { deriveAdaptiveMandate } from './mandate';

const profile: InvestmentProfileInput = {
  goals: ['capital_growth'],
  intended_capital: null,
  time_horizon: 'swing',
  liquidity_need: 'moderate',
  investing_experience: 'intermediate',
  trading_experience: 'beginner',
  products_traded: ['stocks_etfs', 'crypto_spot'],
  decision_frequency: 'monthly',
  drawdown_response: 'hold',
  holding_periods: ['multi_day'],
  explanation_detail: 'detailed',
  notification_frequency: 'opportunities_only',
  disclosures_accepted: false,
};

describe('deriveAdaptiveMandate', () => {
  it('keeps new investors spot-first and capital protective', () => {
    const mandate = deriveAdaptiveMandate({
      ...profile,
      investing_experience: 'none',
      trading_experience: 'none',
      products_traded: ['stocks_etfs'],
      decision_frequency: 'first_time',
      drawdown_response: 'unsure',
    });

    expect(mandate).toEqual(expect.objectContaining({
      risk_posture: 'capital_protective',
      max_loss_per_trade_pct: '0.005',
      max_leverage: '1',
      derivatives_eligible: false,
    }));
  });

  it('allows a bounded derivatives mandate only with advanced relevant experience', () => {
    const mandate = deriveAdaptiveMandate({
      ...profile,
      liquidity_need: 'low',
      investing_experience: 'advanced',
      trading_experience: 'advanced',
      products_traded: ['stocks_etfs', 'crypto_spot', 'futures'],
      decision_frequency: 'weekly',
    });

    expect(mandate).toEqual(expect.objectContaining({
      risk_posture: 'selective_growth',
      max_loss_per_trade_pct: '0.01',
      max_leverage: '20',
      derivatives_eligible: true,
    }));
  });
});
