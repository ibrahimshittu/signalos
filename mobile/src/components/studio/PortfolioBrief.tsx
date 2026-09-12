import { StyleSheet, View } from 'react-native';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { Change, LoadingBlock, Metric, Sparkline, StatusBadge, Text } from '@/components/ui';
import { changeSince, describeWindow, exposureRatio, isStale } from '@/domain/portfolio';
import type { EquitySnapshot } from '@/domain/portfolio';
import type { BrokerPosition, PortfolioSummary } from '@/domain/studio';
import { formatRelativeIso, formatSignedRatioPct, formatSignedUsd, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';
import { CapitalSplit } from './CapitalSplit';
import { PositionBreakdown } from './PositionBreakdown';

interface Props {
  summary: PortfolioSummary | null | undefined;
  history: EquitySnapshot[];
  loading: boolean;
  /** Set when there is no healthy connection to read a portfolio from. */
  disconnected: boolean;
  /** Passed in rather than read during render, so the component stays pure. */
  now: number;
  positions: BrokerPosition[];
  onSync(): void;
  syncing: boolean;
}

const SPARKLINE_WIDTH = 116;
const SPARKLINE_HEIGHT = 48;
const HOUR = 3_600_000;

/**
 * The first thing on the home screen is the user's money.
 *
 * Every figure states where it came from and how fresh it is. The change line
 * is omitted entirely — rather than shown as zero — until a real baseline
 * exists, and the sparkline draws nothing until there are two captures.
 */
export function PortfolioBrief({
  disconnected,
  history,
  loading,
  now,
  onSync,
  positions,
  summary,
  syncing,
}: Props) {
  if (loading && !summary) return <LoadingBlock lines={2} />;

  // A degraded connection still has real balances worth showing; the health of
  // the connection itself is reported separately, right below.
  if (!summary) {
    return (
      <View style={styles.block}>
        <Text tone="secondary" variant="subhead">
          Portfolio value
        </Text>
        <Text style={styles.placeholder} tone="tertiary" variant="hero">
          —
        </Text>
        <StatusBadge
          label={disconnected ? 'No provider connected' : 'Portfolio unavailable'}
          symbol="link.badge.plus"
          tone="caution"
        />
        <Text style={styles.note} tone="secondary" variant="footnote">
          {disconnected
            ? 'Connect a provider to let SignalOS read balances and size proposals against real capital.'
            : 'The last sync did not return balances. Nothing has changed in your account.'}
        </Text>
      </View>
    );
  }

  const equity = Number(summary.total_equity);
  const change = changeSince(history, equity, now);
  const stale = isStale(summary, now);
  const trend = history.map((point) => point.equity);

  return (
    <View>
      <View style={styles.headline}>
        <View style={styles.headlineCopy}>
          <Metric
            accessibilityLabel={`Portfolio value ${formatUsd(equity, { cents: true })}`}
            label="Portfolio value"
            size="hero"
            value={formatUsd(equity, { cents: true })}
          />
        </View>
        {trend.length > 1 ? (
          <Sparkline
            height={SPARKLINE_HEIGHT}
            label={`Portfolio trend over the last ${Math.round((now - history[0].at) / HOUR)} hours`}
            style={styles.sparkline}
            values={trend}
            width={SPARKLINE_WIDTH}
          />
        ) : null}
      </View>

      {change ? (
        <View style={styles.change}>
          <Change
            formatted={`${formatSignedUsd(change.absolute)}   ${formatSignedRatioPct(change.ratio)}`}
            period={describeWindow(change)}
            value={change.absolute}
          />
        </View>
      ) : null}

      <View style={styles.sourceRow}>
        {stale ? (
          <StatusBadge
            label={`Last synced ${formatRelativeIso(summary.captured_at, now)}`}
            tone="caution"
          />
        ) : (
          <Text style={styles.source} tone="tertiary" variant="footnote">
            Bybit{summary.environment === 'testnet' ? ' Testnet' : ''} · synced{' '}
            {formatRelativeIso(summary.captured_at, now)}
          </Text>
        )}
        <HeaderButton
          label="Sync portfolio"
          loading={syncing}
          onPress={onSync}
          symbol="arrow.clockwise"
        />
      </View>

      <View style={styles.capital}>
        <CapitalSplit
          available={Number(summary.available_balance)}
          exposure={exposureRatio(summary)}
          used={Number(summary.invested_value)}
        />
        <PositionBreakdown positions={positions} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: tokens.space.md },
  placeholder: { marginTop: tokens.space.xs },
  note: { maxWidth: 460 },
  headline: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'flex-end',
    gap: tokens.space.base,
  },
  headlineCopy: { flexGrow: 1, flexBasis: 180 },
  // Lifts the chart off the descender line so it reads level with the figure.
  sparkline: { marginBottom: tokens.space.xs },
  change: { marginTop: tokens.space.md },
  sourceRow: {
    marginTop: tokens.space.sm,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.space.md,
  },
  source: { flexShrink: 1 },
  capital: {
    marginTop: tokens.space.xl,
    paddingTop: tokens.space.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: tokens.color.border.hairline,
  },
});
