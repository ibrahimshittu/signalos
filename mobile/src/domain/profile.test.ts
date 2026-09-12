import { describe, expect, it } from '@jest/globals';
import { profileSteps } from '@/components/onboarding/questions';
import { emptyProfileDraft, toProfileInput } from './profile';

describe('investment profile onboarding', () => {
  it('keeps the questionnaire focused and never asks for capital', () => {
    expect(profileSteps.map((step) => step.id)).toEqual([
      'objective',
      'context',
      'investing',
      'trading',
      'products',
      'holding',
      'drawdown',
    ]);
    expect(profileSteps).toHaveLength(7);
    expect(profileSteps.every((step) => !('capital' in step))).toBe(true);
  });

  it('derives low-friction preferences without inventing a capital balance', () => {
    const profile = toProfileInput({
      ...emptyProfileDraft,
      objective: 'capital_growth',
      time_horizon: 'swing',
      liquidity_need: 'moderate',
      investing_experience: 'intermediate',
      trading_experience: 'intermediate',
      products_traded: ['stocks_etfs', 'crypto_spot'],
      holding_period: 'multi_day',
      drawdown_response: 'reduce',
    });

    expect(profile).toMatchObject({
      intended_capital: null,
      decision_frequency: 'weekly',
      explanation_detail: 'standard',
      notification_frequency: 'opportunities_only',
    });
  });
});
