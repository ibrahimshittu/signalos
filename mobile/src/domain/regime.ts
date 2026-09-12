import type { MarketScan } from './studio';

export type RegimeLabel = 'broad_advance' | 'mixed' | 'broad_decline' | 'unclear';

export interface MarketRegime {
  label: RegimeLabel;
  /** Short heading, e.g. "Broad advance". */
  title: string;
  /** One factual sentence. No forecast, no advice. */
  summary: string;
  advancing: number;
  declining: number;
  universe: number;
  /** Median absolute 24h move across the scanned universe, as a ratio. */
  dispersion: number;
  observedAt: string;
}

const titles: Record<RegimeLabel, string> = {
  broad_advance: 'Broad advance',
  mixed: 'Mixed breadth',
  broad_decline: 'Broad decline',
  unclear: 'Not established',
};

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle];
}

/**
 * Describes the current market regime from the latest deterministic scan.
 *
 * This is derived on the client and is labelled as such in the UI: the backend
 * publishes the scan, not a regime. It states breadth and dispersion as
 * observed facts and never implies what will happen next.
 */
export function deriveMarketRegime(scan: MarketScan | null | undefined): MarketRegime | null {
  const universe = scan?.result.hot_universe ?? [];
  if (!scan || universe.length === 0) return null;

  const changes = universe.map((candidate) => Number(candidate.price_change_24h));
  const advancing = changes.filter((change) => change > 0).length;
  const declining = changes.filter((change) => change < 0).length;
  const dispersion = median(changes.map(Math.abs));
  const breadth = advancing / universe.length;

  const label: RegimeLabel =
    universe.length < 3 ? 'unclear' : breadth >= 0.65 ? 'broad_advance' : breadth <= 0.35 ? 'broad_decline' : 'mixed';

  const movement = `Typical 24-hour move ${(dispersion * 100).toFixed(1)}%.`;
  const breadthText = `${advancing} of ${universe.length} scanned markets advancing`;
  const summary =
    label === 'unclear'
      ? 'Too few liquid markets in the current scan to characterise breadth.'
      : `${breadthText}. ${movement}`;

  return {
    label,
    title: titles[label],
    summary,
    advancing,
    declining,
    universe: universe.length,
    dispersion,
    observedAt: scan.observed_at,
  };
}
