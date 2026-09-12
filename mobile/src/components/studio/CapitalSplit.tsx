import { StyleSheet, View } from 'react-native';
import { Text } from '@/components/ui';
import { formatShare, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

interface Props {
  available: number;
  used: number;
  /** Share of equity unavailable for new orders, when equity is known. */
  exposure: number | null;
}

/**
 * How the portfolio is divided between working capital and dry powder.
 *
 * The bar is proportional to the real amounts, so the split is legible before
 * either number is read — and both numbers are still stated in full, because
 * a bar alone is not an amount.
 */
export function CapitalSplit({ available, used, exposure }: Props) {
  const total = available + used;
  return (
    <View>
      <View
        accessibilityLabel={`${formatUsd(used, { cents: true })} in use, ${formatUsd(available, { cents: true })} available`}
        accessible
        style={styles.bar}
      >
        <View style={[styles.segment, styles.used, { flex: total > 0 ? used : 1 }]} />
        <View style={[styles.segment, styles.available, { flex: total > 0 ? available : 1 }]} />
      </View>

      <View style={styles.legend}>
        <Item
          label="Funds in use"
          tint={tokens.color.accent.base}
          value={formatUsd(used, { cents: true })}
          detail={exposure === null ? undefined : `${formatShare(exposure)} of portfolio`}
        />
        <Item
          label="Available"
          tint={tokens.color.border.strong}
          value={formatUsd(available, { cents: true })}
        />
      </View>
    </View>
  );
}

function Item({
  detail,
  label,
  tint,
  value,
}: {
  detail?: string;
  label: string;
  tint: string;
  value: string;
}) {
  return (
    <View style={styles.item}>
      <View style={styles.itemHeader}>
        <View style={[styles.dot, { backgroundColor: tint }]} />
        <Text style={styles.itemLabel} tone="tertiary" variant="caption">
          {label}
        </Text>
      </View>
      <Text fit numeric style={styles.itemValue} variant="title3">
        {value}
      </Text>
      {detail ? (
        <Text style={styles.itemDetail} tone="tertiary" variant="footnote">
          {detail}
        </Text>
      ) : null}
    </View>
  );
}

const DOT = 6;
const BAR = 8;
/** Aligns the value under the label rather than under the dot. */
const TEXT_INDENT = DOT + tokens.space.sm;

const styles = StyleSheet.create({
  bar: { height: BAR, flexDirection: 'row', gap: tokens.optical.tick },
  segment: { height: BAR, borderRadius: tokens.radius.full, minWidth: tokens.space.xs },
  used: { backgroundColor: tokens.color.accent.base },
  available: { backgroundColor: tokens.color.border.strong },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: tokens.space.lg,
    marginTop: tokens.space.base,
  },
  item: { flexGrow: 1, flexBasis: 140 },
  itemHeader: { flexDirection: 'row', alignItems: 'center', gap: tokens.space.sm },
  dot: { width: DOT, height: DOT, borderRadius: tokens.radius.full },
  itemLabel: { flexShrink: 1 },
  itemValue: { marginTop: tokens.space.xs, marginLeft: TEXT_INDENT },
  itemDetail: { marginTop: tokens.optical.nudge, marginLeft: TEXT_INDENT },
});
