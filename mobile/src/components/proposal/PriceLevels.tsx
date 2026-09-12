import { StyleSheet, View } from 'react-native';
import { Card, CardRow, Text } from '@/components/ui';
import { entryPrice, rewardRisk } from '@/domain/proposal';
import type { TradeProposal } from '@/domain/studio';
import { formatSignedRatioPct, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

/**
 * The plan the strategy calculated: where it enters, where it is proven wrong,
 * and where it takes profit.
 *
 * The scale above the numbers is drawn to the real distances, so the shape of
 * the trade — how much room it gives the idea versus how much it risks — is
 * legible before a single figure is read.
 *
 * Every value here is read-only. Editing any one of them would be a different
 * trade, which the platform requires to be a different proposal.
 */
export function PriceLevels({ proposal }: { proposal: TradeProposal }) {
  const entry = entryPrice(proposal);
  const stop = Number(proposal.stop_loss);
  const target = Number(proposal.take_profit);
  const ratio = rewardRisk(proposal);

  const riskDistance = Math.abs(entry - stop);
  const rewardDistance = Math.abs(target - entry);
  const total = riskDistance + rewardDistance;

  return (
    <View>
      <View
        accessibilityLabel={`Risking ${formatUsd(riskDistance)} per unit against a target ${formatUsd(rewardDistance)} away${
          ratio ? `, a reward to risk of ${ratio.toFixed(1)} to 1` : ''
        }`}
        accessible
        style={styles.scale}>
        <View style={[styles.segment, styles.riskSegment, { flex: total > 0 ? riskDistance : 1 }]} />
        <View style={styles.entryMark} />
        <View style={[styles.segment, styles.rewardSegment, { flex: total > 0 ? rewardDistance : 1 }]} />
      </View>

      <View style={styles.legend}>
        <Text tone="loss" variant="caption">
          Risk
        </Text>
        {ratio === null ? null : (
          <Text numeric variant="caption">
            {ratio.toFixed(1)} : 1
          </Text>
        )}
        <Text tone="gain" variant="caption">
          Reward
        </Text>
      </View>

      <Card style={styles.card}>
        <CardRow
          detail={proposal.order_type === 'limit' ? 'Limit order' : 'Market order'}
          label="Entry"
          value={formatUsd(entry, { cents: true })}
        />
        <CardRow
          detail="The idea is wrong here"
          label="Invalidation stop"
          tone="loss"
          value={`${formatUsd(stop, { cents: true })}   ${formatSignedRatioPct((stop - entry) / entry)}`}
        />
        <CardRow
          detail="The plan takes profit here"
          label="Target"
          tone="gain"
          value={`${formatUsd(target, { cents: true })}   ${formatSignedRatioPct((target - entry) / entry)}`}
        />
        <CardRow
          detail="Calculated by the strategy, not chosen by you"
          label="Reward to risk"
          last
          value={ratio === null ? 'Not applicable' : `${ratio.toFixed(1)} : 1`}
        />
      </Card>

      <Text style={styles.reference} tone="tertiary" variant="footnote">
        Market reference {formatUsd(Number(proposal.market_price), { cents: true })} at the time of analysis.
      </Text>
    </View>
  );
}

const BAR = 6;

const styles = StyleSheet.create({
  scale: { flexDirection: 'row', alignItems: 'center', marginTop: tokens.space.base },
  segment: { height: BAR, borderRadius: tokens.radius.full },
  riskSegment: { backgroundColor: tokens.color.finance.lossTint },
  rewardSegment: { backgroundColor: tokens.color.finance.gainTint },
  // The entry sits between the two spans, drawn taller so it reads as a mark.
  entryMark: {
    width: 2,
    height: 12,
    borderRadius: tokens.radius.full,
    backgroundColor: tokens.color.text.primary,
    marginHorizontal: tokens.optical.tick,
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: tokens.space.sm,
  },
  card: { marginTop: tokens.space.base },
  reference: { marginTop: tokens.space.md },
});
