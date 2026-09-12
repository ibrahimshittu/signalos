import { memo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Glyph, Text, Touchable } from '@/components/ui';
import { changeGlyph } from '@/components/ui/Glyph';
import { baseSymbol, quoteSymbol } from '@/domain/proposal';
import type { MarketCandidate } from '@/domain/studio';
import { formatCompactUsd, formatSignedRatioPct } from '@/lib/format';
import { colorForChange, tokens } from '@/theme/tokens';

const categoryLabels: Record<MarketCandidate['category'], string> = {
  linear: 'Perpetual',
  spot: 'Spot',
};

const CHANGE_COLUMN = 92;

/**
 * A scanned market. Read-only: nothing here can start a trade.
 *
 * Price change aligns in one value column. Activity determines the ranking;
 * its full metrics remain in the detail sheet instead of crowding the row.
 */
export const MarketRow = memo(function MarketRow({
  candidate,
  onPress,
}: {
  candidate: MarketCandidate;
  onPress(): void;
}) {
  const change = Number(candidate.price_change_24h);
  const activity = Math.round(Number(candidate.activity_score) * 100);
  const tint = colorForChange(change);

  return (
    <Touchable
      accessibilityHint="Opens turnover, activity, and spread for this market"
      accessibilityLabel={`${baseSymbol(candidate.symbol)}, ${formatSignedRatioPct(change)} over 24 hours, activity ${activity} of 100`}
      accessibilityRole="button"
      feedback="highlight"
      onPress={onPress}
      style={styles.row}
    >
      <View style={styles.market}>
        <Text variant="headline">
          {baseSymbol(candidate.symbol)}
          <Text tone="tertiary" variant="subhead">
            {' / '}
            {quoteSymbol(candidate.symbol)}
          </Text>
        </Text>
        <Text style={styles.meta} tone="tertiary" variant="footnote">
          {formatCompactUsd(Number(candidate.turnover_24h))} turnover ·{' '}
          {categoryLabels[candidate.category]}
        </Text>
      </View>

      <View style={styles.change}>
        <Glyph color={tint} name={changeGlyph(change)} size={11} />
        <Text numeric style={{ color: tint }} variant="subhead">
          {formatSignedRatioPct(change)}
        </Text>
      </View>

      <Glyph color={tokens.color.text.tertiary} name="chevron.right" size={13} />
    </Touchable>
  );
});

export function MarketColumns() {
  return (
    <View style={styles.columns}>
      <Text style={styles.market} tone="tertiary" variant="caption">
        Market · ranked by activity
      </Text>
      <Text style={styles.changeLabel} tone="tertiary" variant="caption">
        24h
      </Text>
      {/* Reserves the width the row's chevron occupies, so the column headers
          stay aligned with the values beneath them. */}
      <View style={styles.chevronSpacer} />
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.md,
    paddingHorizontal: tokens.space.sm,
    marginHorizontal: -tokens.space.sm,
    paddingVertical: tokens.space.md + tokens.optical.nudge,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: tokens.color.border.hairline,
    minHeight: tokens.layout.touch + tokens.space.md,
  },
  columns: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: tokens.space.md,
    paddingBottom: tokens.space.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: tokens.color.border.hairline,
  },
  market: { flex: 1 },
  meta: { marginTop: tokens.optical.nudge },
  change: {
    minWidth: CHANGE_COLUMN,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: tokens.optical.nudge,
  },
  changeLabel: { minWidth: CHANGE_COLUMN, textAlign: 'right' },
  chevronSpacer: { width: 13 },
});
