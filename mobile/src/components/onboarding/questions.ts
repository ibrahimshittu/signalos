import type { ProfileDraft } from '@/domain/profile';
import type {
  DecisionFrequency,
  DrawdownResponse,
  ExperienceLevel,
  ExplanationDetail,
  HoldingPeriod,
  InvestmentGoal,
  NotificationFrequency,
  TradedProduct,
} from '@/domain/studio';

export interface Choice {
  value: string;
  title: string;
  detail?: string;
}

export interface ProfileStep {
  id: string;
  /** The question itself. Always a question, never a command. */
  title: string;
  /** Why it is being asked, and what it will and will not change. */
  body: string;
  options: Choice[];
  multiple?: boolean;
  selected(draft: ProfileDraft): string[];
  apply(draft: ProfileDraft, value: string): Partial<ProfileDraft>;
  complete(draft: ProfileDraft): boolean;
}

const investingExperienceChoices: { value: ExperienceLevel; title: string; detail: string }[] = [
  { value: 'none', title: 'I am just getting started', detail: 'I have not managed investments myself yet.' },
  { value: 'beginner', title: 'I know the basics', detail: 'I have bought a few investments and understand gains and losses.' },
  { value: 'intermediate', title: 'I invest regularly', detail: 'I have stayed invested through different market conditions.' },
  { value: 'advanced', title: 'I am highly experienced', detail: 'I evaluate risk, allocation, and portfolio exposure.' },
];

const tradingExperienceChoices: { value: ExperienceLevel; title: string; detail: string }[] = [
  { value: 'none', title: 'I have not traded actively', detail: 'Entries, stops, and order types are new to me.' },
  { value: 'beginner', title: 'I have placed a few trades', detail: 'I understand basic orders and position risk.' },
  { value: 'intermediate', title: 'I trade regularly', detail: 'I have managed entries and exits in changing markets.' },
  { value: 'advanced', title: 'I am highly experienced', detail: 'I actively manage execution, leverage, and portfolio risk.' },
];

const objectives: { value: InvestmentGoal; title: string; detail: string }[] = [
  { value: 'capital_growth', title: 'Grow capital over time', detail: 'Accept measured risk in exchange for long-run growth.' },
  { value: 'income', title: 'Generate supplemental income', detail: 'Prefer repeatable opportunities over large single bets.' },
  { value: 'capital_preservation', title: 'Protect what I already have', detail: 'Defensive by default, and comfortable with frequent no-trade results.' },
  { value: 'learning', title: 'Learn before committing more', detail: 'Prioritise explanation and the most protective starting posture.' },
];

/** Horizon and liquidity are asked together because people think of them together. */
const contexts: { value: string; title: string; detail: string; horizon: ProfileDraft['time_horizon']; liquidity: ProfileDraft['liquidity_need'] }[] = [
  {
    value: 'spare',
    title: 'Not for several years',
    detail: 'I can leave this capital invested through long market cycles.',
    horizon: 'long_term',
    liquidity: 'low',
  },
  {
    value: 'medium',
    title: 'Within one or two years',
    detail: 'There is no fixed date, but I want it reasonably accessible.',
    horizon: 'medium_term',
    liquidity: 'moderate',
  },
  {
    value: 'active',
    title: 'I actively trade it',
    detail: 'I expect to move between positions over days and weeks.',
    horizon: 'swing',
    liquidity: 'moderate',
  },
  {
    value: 'needed',
    title: 'At short notice',
    detail: 'I may need this capital elsewhere, so it must stay accessible.',
    horizon: 'intraday',
    liquidity: 'high',
  },
];

const products: { value: TradedProduct; title: string }[] = [
  { value: 'stocks_etfs', title: 'Stocks and ETFs' },
  { value: 'crypto_spot', title: 'Crypto spot' },
  { value: 'options', title: 'Options' },
  { value: 'futures', title: 'Futures or perpetuals' },
  { value: 'forex', title: 'Foreign exchange' },
  { value: 'managed_portfolios', title: 'Managed portfolios' },
];

const frequencies: { value: DecisionFrequency; title: string; detail: string }[] = [
  { value: 'first_time', title: 'This would be my first', detail: 'SignalOS should begin with the most cautious context.' },
  { value: 'few_per_year', title: 'A few times a year', detail: 'I make occasional, considered decisions.' },
  { value: 'monthly', title: 'A few times a month', detail: 'I review markets and positions regularly.' },
  { value: 'weekly', title: 'Most weeks', detail: 'I actively manage opportunities and exposure.' },
  { value: 'daily', title: 'Most trading days', detail: 'I am comfortable following fast-moving positions.' },
];

const holdingPeriods: { value: HoldingPeriod; title: string; detail: string }[] = [
  { value: 'intraday', title: 'Hours', detail: 'I prefer to be flat by the end of the day.' },
  { value: 'multi_day', title: 'Days', detail: 'I hold through a few sessions.' },
  { value: 'multi_week', title: 'Weeks', detail: 'I give a thesis room to play out.' },
  { value: 'long_term', title: 'Months or longer', detail: 'I hold unless the reasoning breaks.' },
];

const drawdowns: { value: DrawdownResponse; title: string; detail: string }[] = [
  { value: 'exit', title: 'I usually exit', detail: 'Protecting capital quickly matters most to me.' },
  { value: 'reduce', title: 'I reduce the position', detail: 'I lower exposure while I reassess.' },
  { value: 'hold', title: 'I follow the original plan', detail: 'I stay with a valid thesis and its predefined invalidation.' },
  { value: 'add', title: 'I may add selectively', detail: 'Only when the thesis is intact and portfolio risk allows it.' },
  { value: 'unsure', title: 'I am not sure yet', detail: 'SignalOS should assume a protective posture until it learns.' },
];

const explanations: { value: ExplanationDetail; title: string; detail: string }[] = [
  { value: 'concise', title: 'Just the decision', detail: 'The plan, the risk, and the single strongest counter-argument.' },
  { value: 'standard', title: 'Balanced', detail: 'The reasoning and the evidence behind it, without the full workings.' },
  { value: 'detailed', title: 'Show me everything', detail: 'Full evidence, gate results, and the calculations behind sizing.' },
];

const notifications: { value: NotificationFrequency; title: string; detail: string }[] = [
  { value: 'critical_only', title: 'Only what needs me', detail: 'Expiring approvals, connection failures, and risk events.' },
  { value: 'opportunities_only', title: 'New proposals too', detail: 'Told when something clears every gate, plus anything critical.' },
  { value: 'daily_digest', title: 'A daily summary', detail: 'One recap a day, plus anything genuinely urgent.' },
];

/** Sentinel for "I have not traded any of these" — distinct from unanswered. */
const NO_PRODUCTS = 'none';

export const profileSteps: ProfileStep[] = [
  {
    id: 'objective',
    title: 'What are you investing toward?',
    body: 'Your objective decides how opportunities are ranked and how trade-offs are explained. It does not unlock better returns.',
    options: objectives,
    selected: (draft) => (draft.objective ? [draft.objective] : []),
    apply: (_draft, value) => ({ objective: value as InvestmentGoal }),
    complete: (draft) => draft.objective !== null,
  },
  {
    id: 'context',
    title: 'When might you need this capital?',
    body: 'This keeps proposals inside a holding window you can actually live with.',
    options: contexts,
    selected: (draft) => {
      const match = contexts.find(
        (context) => context.horizon === draft.time_horizon && context.liquidity === draft.liquidity_need,
      );
      return match ? [match.value] : [];
    },
    apply: (_draft, value) => {
      const context = contexts.find((item) => item.value === value)!;
      return { time_horizon: context.horizon, liquidity_need: context.liquidity };
    },
    complete: (draft) => draft.time_horizon !== null && draft.liquidity_need !== null,
  },
  {
    id: 'investing',
    title: 'How familiar are you with investing?',
    body: 'Think about stocks, funds, crypto, or any portfolio you have managed yourself.',
    options: investingExperienceChoices,
    selected: (draft) => (draft.investing_experience ? [draft.investing_experience] : []),
    apply: (_draft, value) => ({ investing_experience: value as ExperienceLevel }),
    complete: (draft) => draft.investing_experience !== null,
  },
  {
    id: 'trading',
    title: 'How much active trading have you done?',
    body: 'Think about choosing entries, exits, stops, and order types yourself.',
    options: tradingExperienceChoices,
    selected: (draft) => (draft.trading_experience ? [draft.trading_experience] : []),
    apply: (_draft, value) => ({ trading_experience: value as ExperienceLevel }),
    complete: (draft) => draft.trading_experience !== null,
  },
  {
    id: 'products',
    title: 'Which markets have you used?',
    body: 'Select all that apply. Paper trading counts here too.',
    options: [...products, { value: NO_PRODUCTS, title: 'None of these yet' }],
    multiple: true,
    selected: (draft) => {
      if (draft.products_traded === null) return [];
      return draft.products_traded.length ? draft.products_traded : [NO_PRODUCTS];
    },
    apply: (draft, value) => {
      if (value === NO_PRODUCTS) return { products_traded: [] };
      const current = draft.products_traded ?? [];
      const product = value as TradedProduct;
      return {
        products_traded: current.includes(product)
          ? current.filter((item) => item !== product)
          : [...current, product],
      };
    },
    complete: (draft) => draft.products_traded !== null,
  },
  {
    id: 'holding',
    title: 'How long do you prefer to hold?',
    body: 'SignalOS will favor setups that match your natural decision rhythm.',
    options: holdingPeriods,
    selected: (draft) => (draft.holding_period ? [draft.holding_period] : []),
    apply: (_draft, value) => ({ holding_period: value as HoldingPeriod }),
    complete: (draft) => draft.holding_period !== null,
  },
  {
    id: 'drawdown',
    title: 'When a position moves against you, what feels natural?',
    body: 'There is no right answer. This helps SignalOS start with the right level of caution.',
    options: drawdowns,
    selected: (draft) => (draft.drawdown_response ? [draft.drawdown_response] : []),
    apply: (_draft, value) => ({ drawdown_response: value as DrawdownResponse }),
    complete: (draft) => draft.drawdown_response !== null,
  },
];

const choiceTitle = (choices: Choice[], value: string | null): string =>
  choices.find((choice) => choice.value === value)?.title ?? 'Not set';

/** The user's answers, phrased for review on the Account screen. */
export function profileAnswers(draft: ProfileDraft): { label: string; value: string }[] {
  const context = contexts.find(
    (item) => item.horizon === draft.time_horizon && item.liquidity === draft.liquidity_need,
  );
  const traded = draft.products_traded;
  return [
    { label: 'Objective', value: choiceTitle(objectives, draft.objective) },
    { label: 'What this money is for', value: context?.title ?? 'Not set' },
    { label: 'Investing experience', value: choiceTitle(investingExperienceChoices, draft.investing_experience) },
    { label: 'Trading experience', value: choiceTitle(tradingExperienceChoices, draft.trading_experience) },
    {
      label: 'Markets used',
      value: traded === null ? 'Not set' : traded.length === 0 ? 'None yet' : traded.map((item) => choiceTitle(products, item)).join(', '),
    },
    { label: 'Decision rhythm', value: choiceTitle(frequencies, draft.decision_frequency) },
    { label: 'Typical holding period', value: choiceTitle(holdingPeriods, draft.holding_period) },
    { label: 'During a drawdown', value: choiceTitle(drawdowns, draft.drawdown_response) },
    { label: 'Explanation depth', value: choiceTitle(explanations, draft.explanation_detail) },
    { label: 'Notifications', value: choiceTitle(notifications, draft.notification_frequency) },
  ];
}
