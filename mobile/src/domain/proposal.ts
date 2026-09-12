import type { BrokerOrderState, PortfolioSummary, ProposalStatus, TradeProposal } from './studio';

/** The price the plan is built around: the limit if set, otherwise the market. */
export function entryPrice(proposal: TradeProposal): number {
  return Number(proposal.limit_price ?? proposal.market_price);
}

/**
 * Reward-to-risk implied by the strategy's own stop and target.
 *
 * The user never sets these. This restates what the system calculated so the
 * decision can be checked, not configured.
 */
export function rewardRisk(proposal: TradeProposal): number | null {
  const entry = entryPrice(proposal);
  const risk = Math.abs(entry - Number(proposal.stop_loss));
  const reward = Math.abs(Number(proposal.take_profit) - entry);
  return risk > 0 ? reward / risk : null;
}

/** Share of portfolio equity the estimated maximum loss represents. */
export function portfolioEffect(
  proposal: TradeProposal,
  summary: PortfolioSummary | null | undefined,
): number | null {
  const equity = Number(summary?.total_equity ?? 0);
  if (!summary || !Number.isFinite(equity) || equity <= 0) return null;
  return Number(proposal.estimated_max_loss) / equity;
}

export type ExpiryState = 'open' | 'closing' | 'expired';

export interface Expiry {
  state: ExpiryState;
  minutes: number;
  /** Plain statement of fact. Deliberately not a live countdown. */
  label: string;
}

/**
 * Expiry is stated, never dramatised. There is no ticking clock and no colour
 * escalation until the terms are genuinely within a few minutes of lapsing.
 */
export function expiryState(proposal: TradeProposal, now: Date = new Date()): Expiry {
  const remaining = Math.round((new Date(proposal.expires_at).getTime() - now.getTime()) / 60_000);
  if (remaining <= 0) return { state: 'expired', minutes: 0, label: 'Terms expired' };
  if (remaining <= 5)
    return { state: 'closing', minutes: remaining, label: `Terms lapse in ${remaining}m` };
  if (remaining < 60)
    return { state: 'open', minutes: remaining, label: `Terms valid ${remaining}m` };
  const hours = Math.floor(remaining / 60);
  return { state: 'open', minutes: remaining, label: `Terms valid ${hours}h` };
}

export interface StatusPresentation {
  label: string;
  tone: 'neutral' | 'active' | 'positive' | 'caution' | 'critical';
  /** What the state means, in the user's terms. */
  meaning: string;
}

const statuses: Record<ProposalStatus, StatusPresentation> = {
  available: {
    label: 'Awaiting your decision',
    tone: 'active',
    meaning: 'Nothing has been sent to your broker.',
  },
  rejected: { label: 'Passed', tone: 'neutral', meaning: 'You declined this proposal.' },
  expired: { label: 'Expired', tone: 'neutral', meaning: 'The terms lapsed before a decision.' },
  submitted: {
    label: 'Submitted',
    tone: 'active',
    meaning: 'Submission was recorded. Check the broker order for its outcome.',
  },
  invalidated: {
    label: 'Terms changed',
    tone: 'caution',
    meaning: 'Market or account state changed, so nothing was submitted.',
  },
  archived: {
    label: 'Archived',
    tone: 'neutral',
    meaning: 'This proposal is retained as a record. Its order outcome is recorded separately.',
  },
};

export function statusPresentation(status: ProposalStatus): StatusPresentation {
  return (
    statuses[status] ?? {
      label: 'Status unavailable',
      tone: 'caution',
      meaning: 'Refresh to check this proposal.',
    }
  );
}

const orderStatuses: Record<BrokerOrderState, StatusPresentation> = {
  submitting: {
    label: 'Submitting',
    tone: 'active',
    meaning: 'The order is being sent. Acceptance is not confirmed yet.',
  },
  acknowledged: {
    label: 'Order accepted',
    tone: 'positive',
    meaning: 'Bybit accepted the order. It may not have filled yet.',
  },
  partially_filled: {
    label: 'Partially filled',
    tone: 'positive',
    meaning: 'Bybit reports that part of the order has filled.',
  },
  filled: {
    label: 'Order filled',
    tone: 'positive',
    meaning: 'Bybit reports that the order has filled. This does not mean the position is closed.',
  },
  cancelling: {
    label: 'Cancellation pending',
    tone: 'active',
    meaning: 'Cancellation was requested. The order can still fill until Bybit confirms.',
  },
  cancelled: {
    label: 'Order cancelled',
    tone: 'neutral',
    meaning: 'Bybit cancelled the remaining order. Any earlier fills remain.',
  },
  rejected: {
    label: 'Order rejected',
    tone: 'caution',
    meaning: 'The order was rejected. No successful submission was confirmed.',
  },
  submission_unknown: {
    label: 'Submission not confirmed',
    tone: 'caution',
    meaning: 'The order may have reached Bybit. Check status before trying again.',
  },
  reconciliation_required: {
    label: 'Checking broker records',
    tone: 'caution',
    meaning: 'The final outcome is not confirmed. Do not assume the order failed.',
  },
};

export function orderStatusPresentation(state: BrokerOrderState): StatusPresentation {
  return (
    orderStatuses[state] ?? {
      label: 'Order status unavailable',
      tone: 'caution',
      meaning: 'Refresh to check the broker record.',
    }
  );
}

export function isAwaitingDecision(proposal: TradeProposal): boolean {
  return proposal.status === 'available';
}

/** Proposal lifecycle only. Fills and open positions come from broker records. */
export type ProposalPhase = 'awaiting' | 'submitted' | 'closed';

export function proposalPhase(proposal: TradeProposal): ProposalPhase {
  if (isAwaitingDecision(proposal)) return 'awaiting';
  return proposal.status === 'submitted' ? 'submitted' : 'closed';
}

export function isSubmitted(proposal: TradeProposal): boolean {
  return proposal.status === 'submitted';
}

/** "BTC" from "BTCUSDT" — the quote asset is shown separately. */
export function baseSymbol(symbol: string): string {
  return symbol.replace(/USDT$|USDC$|USD$/, '');
}

export function quoteSymbol(symbol: string): string {
  return symbol.slice(baseSymbol(symbol).length) || 'USDT';
}

export function directionLabel(side: TradeProposal['side']): string {
  return side === 'buy' ? 'Long' : 'Short';
}

/** Strategy families arrive as snake_case identifiers; show them as words. */
export function strategyLabel(family: string): string {
  const words = family.replaceAll('_', ' ');
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export interface EvidenceState {
  label: string;
  tone: 'positive' | 'caution';
  detail: string;
}

/** The deterministic gate report, expressed as a confidence statement. */
export function evidenceState(proposal: TradeProposal): EvidenceState {
  if (proposal.gate_report.passed) {
    return {
      label: 'All gates cleared',
      tone: 'positive',
      detail: 'Strategy, evidence, quantitative, portfolio, and risk gates all passed.',
    };
  }
  const count = proposal.gate_report.failures.length;
  return {
    label: `${count} gate${count === 1 ? '' : 's'} flagged`,
    tone: 'caution',
    detail: proposal.gate_report.failures.join(', '),
  };
}
