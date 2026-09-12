import { StyleSheet, View } from 'react-native';
import { router } from 'expo-router';
import { Change, Text, Touchable } from '@/components/ui';
import type { BrokerPosition } from '@/domain/studio';
import { formatSignedUsd, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

interface Props {
  positions: BrokerPosition[];
}

/** Reconciled Bybit positions explaining where portfolio exposure currently sits. */
export function PositionBreakdown({ positions }: Props) {
  if (!positions.length) return null;

  return (
    <View style={styles.block}>
      <Text tone="tertiary" variant="caption">
        Open positions · {positions.length}
      </Text>
      <View style={styles.list}>
        {positions.map((position) => {
          const pnl = Number(position.unrealised_pnl);
          return (
            <Touchable
              key={position.id}
              style={styles.row}
              accessibilityRole="button"
              accessibilityLabel={`Manage ${position.symbol} position`}
              onPress={() =>
                router.push({ pathname: '/position/[id]', params: { id: position.id } })
              }
            >
              <View style={styles.copy}>
                <Text fit numeric variant="headline">
                  {position.symbol.replace(/USDT$/, '')}
                </Text>
                <Text tone="tertiary" variant="footnote">
                  {position.side === 'buy' ? 'Long' : 'Short'} ·{' '}
                  {position.leverage ? `${position.leverage}×` : 'Spot'}
                </Text>
              </View>
              <View style={styles.value}>
                <Text fit numeric variant="headline">
                  {formatUsd(Number(position.position_value), { cents: true })}
                </Text>
                <Change
                  formatted={formatSignedUsd(pnl)}
                  period="unrealised"
                  value={pnl}
                  variant="footnote"
                />
              </View>
            </Touchable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { marginTop: tokens.space.lg },
  list: { marginTop: tokens.space.sm },
  row: {
    minHeight: tokens.layout.touch,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.space.base,
    paddingVertical: tokens.space.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: tokens.color.border.hairline,
  },
  copy: { flex: 1 },
  value: { alignItems: 'flex-end' },
});
