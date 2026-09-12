import { memo } from 'react';
import { StyleSheet, View } from 'react-native';
import { statusGlyph } from '@/components/proposal/statusGlyph';
import { Glyph, StatusBadge, Text, Touchable } from '@/components/ui';
import {
  baseSymbol,
  directionLabel,
  evidenceState,
  expiryState,
  isAwaitingDecision,
  portfolioEffect,
  quoteSymbol,
  statusPresentation,
  strategyLabel,
} from '@/domain/proposal';
import type { PortfolioSummary, TradeProposal } from '@/domain/studio';
import { formatShare, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

interface Props {
  proposal: TradeProposal;
  portfolio: PortfolioSummary | null | undefined;
  onPress(): void;
  /** Passed in rather than read during render, so the row stays pure. */
  now: Date;
}

/**
 * One proposal, compact enough to scan a list of them.
 *
 * Laid out as a ledger line rather than a stack of sentences: identity on the
 * left, money right-aligned on a shared axis so figures compare down the
 * column, and the decision state on its own footer line where it cannot be
 * mistaken for another attribute.
 *
 * It carries everything needed to triage without opening — instrument,
 * direction, strategy, evidence, maximum loss, portfolio effect, expiry, and
 * state — and every line wraps, so large Dynamic Type reflows instead of
 * clipping a financial value.
 */
export const SignalRow = memo(function SignalRow({ now, onPress, portfolio, proposal }: Props) {
  const status = statusPresentation(proposal.status);
  const evidence = evidenceState(proposal);
  const expiry = expiryState(proposal, now);
  const effect = portfolioEffect(proposal, portfolio);
  const awaiting = isAwaitingDecision(proposal);
  const long = proposal.side === 'buy';
  const direction = long ? tokens.color.finance.gain : tokens.color.finance.loss;

  // A flagged gate outranks the clock, and "all gates cleared" is the default
  // state — saying it on every row is noise that pushes the line into a wrap.
  const meta =
    evidence.tone === 'caution'
      ? { text: evidence.label, tone: 'caution' as const }
      : awaiting
        ? {
            text: expiry.label,
            tone: expiry.state === 'open' ? ('tertiary' as const) : ('caution' as const),
          }
        : null;

  return (
    <Touchable
      accessibilityHint="Opens the full case, the opposing case, and the approval controls"
      accessibilityRole="button"
      feedback="highlight"
      onPress={onPress}
      style={styles.row}
    >
      <View style={styles.columns}>
        <View style={styles.identity}>
          <Text variant="headline">
            {baseSymbol(proposal.symbol)}
            <Text tone="tertiary" variant="subhead">
              {' / '}
              {quoteSymbol(proposal.symbol)}
            </Text>
          </Text>

          <View style={styles.direction}>
            <Glyph
              color={direction}
              name={long ? 'arrow.up.right' : 'arrow.down.right'}
              size={12}
            />
            <Text style={{ color: direction }} variant="subhead">
              {directionLabel(proposal.side)}
            </Text>
            <Text tone="tertiary" variant="subhead">
              ·
            </Text>
            <Text style={styles.strategy} tone="secondary" variant="subhead">
              {strategyLabel(proposal.strategy_family)}
            </Text>
          </View>
        </View>

        <View style={styles.money}>
          <Text fit numeric variant="headline">
            {formatUsd(Number(proposal.estimated_max_loss), { cents: true })}
          </Text>
          <Text style={styles.moneyLabel} tone="tertiary" variant="caption">
            est. loss{effect === null ? '' : ` · ${formatShare(effect)}`}
          </Text>
        </View>
      </View>

      <View style={styles.footer}>
        <StatusBadge
          label={status.label}
          symbol={statusGlyph(proposal.status)}
          tone={status.tone}
        />
        {meta ? (
          <Text numeric style={styles.meta} tone={meta.tone} variant="caption">
            {meta.text}
          </Text>
        ) : null}
      </View>
    </Touchable>
  );
});

const styles = StyleSheet.create({
  row: {
    paddingVertical: tokens.space.base,
    paddingHorizontal: tokens.space.sm,
    marginHorizontal: -tokens.space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: tokens.color.border.hairline,
  },
  columns: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'flex-start',
    gap: tokens.space.md,
  },
  identity: { flexGrow: 1, flexBasis: 160, gap: tokens.space.xs },
  direction: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: tokens.space.xs },
  strategy: { flexShrink: 1 },
  // Right-aligned so maximum-loss figures line up down the list and compare.
  money: { alignItems: 'flex-end', minWidth: 96 },
  moneyLabel: { marginTop: tokens.optical.tick },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: tokens.space.sm,
    marginTop: tokens.space.md,
  },
  meta: { flexShrink: 1, textAlign: 'right' },
});
