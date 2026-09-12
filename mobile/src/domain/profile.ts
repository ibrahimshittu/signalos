import type {
  DecisionFrequency,
  DrawdownResponse,
  ExperienceLevel,
  ExplanationDetail,
  HoldingPeriod,
  InvestmentGoal,
  InvestmentProfileInput,
  LiquidityNeed,
  NotificationFrequency,
  TimeHorizon,
  TradedProduct,
} from './studio';

/**
 * The in-progress investment profile.
 *
 * Every answer starts as `null` rather than a default. A suitability
 * questionnaire that pre-selects answers invites people to skip it, and the
 * resulting mandate would be built on assumptions the user never made.
 */
export interface ProfileDraft {
  objective: InvestmentGoal | null;
  time_horizon: TimeHorizon | null;
  liquidity_need: LiquidityNeed | null;
  investing_experience: ExperienceLevel | null;
  trading_experience: ExperienceLevel | null;
  /** `null` is unanswered; `[]` is a deliberate "none of these". */
  products_traded: TradedProduct[] | null;
  decision_frequency: DecisionFrequency | null;
  holding_period: HoldingPeriod | null;
  drawdown_response: DrawdownResponse | null;
  explanation_detail: ExplanationDetail | null;
  notification_frequency: NotificationFrequency | null;
}

export const emptyProfileDraft: ProfileDraft = {
  objective: null,
  time_horizon: null,
  liquidity_need: null,
  investing_experience: null,
  trading_experience: null,
  products_traded: null,
  decision_frequency: null,
  holding_period: null,
  drawdown_response: null,
  explanation_detail: null,
  notification_frequency: null,
};

const frequencyForHoldingPeriod: Record<HoldingPeriod, DecisionFrequency> = {
  intraday: 'daily',
  multi_day: 'weekly',
  multi_week: 'monthly',
  long_term: 'few_per_year',
};

/**
 * Converts a completed draft into the backend payload.
 *
 * Returns null while anything is unanswered, so an incomplete profile can never
 * reach the mandate calculation.
 */
export function toProfileInput(draft: ProfileDraft): InvestmentProfileInput | null {
  if (
    !draft.objective ||
    !draft.time_horizon ||
    !draft.liquidity_need ||
    !draft.investing_experience ||
    !draft.trading_experience ||
    draft.products_traded === null ||
    !draft.holding_period ||
    !draft.drawdown_response
  ) {
    return null;
  }

  return {
    goals: [draft.objective],
    intended_capital: null,
    time_horizon: draft.time_horizon,
    liquidity_need: draft.liquidity_need,
    investing_experience: draft.investing_experience,
    trading_experience: draft.trading_experience,
    products_traded: draft.products_traded,
    decision_frequency: draft.decision_frequency ?? frequencyForHoldingPeriod[draft.holding_period],
    drawdown_response: draft.drawdown_response,
    holding_periods: [draft.holding_period],
    explanation_detail: draft.explanation_detail ?? 'standard',
    notification_frequency: draft.notification_frequency ?? 'opportunities_only',
    disclosures_accepted: false,
  };
}

/** Turns a stored profile back into a draft so answers can be reviewed later. */
export function draftFromProfile(input: InvestmentProfileInput): ProfileDraft {
  return {
    objective: input.goals[0] ?? null,
    time_horizon: input.time_horizon,
    liquidity_need: input.liquidity_need,
    investing_experience: input.investing_experience,
    trading_experience: input.trading_experience,
    products_traded: input.products_traded,
    decision_frequency: input.decision_frequency,
    holding_period: input.holding_periods[0] ?? null,
    drawdown_response: input.drawdown_response,
    explanation_detail: input.explanation_detail,
    notification_frequency: input.notification_frequency,
  };
}

/** Human-readable label for a snake_case enum value. */
export function humanise(value: string | null | undefined, fallback = 'Not set'): string {
  if (!value) return fallback;
  const words = value.replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}
