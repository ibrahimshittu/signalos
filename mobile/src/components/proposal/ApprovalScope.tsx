import { StyleSheet, View } from 'react-native';
import { Glyph, Text } from '@/components/ui';
import { baseSymbol, entryPrice } from '@/domain/proposal';
import type { TradeProposal } from '@/domain/studio';
import { formatClock, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

/**
 * Exactly what approval authorises — nothing more.
 *
 * Written as concrete statements rather than legal prose, because the point is
 * that the user can check each one against the plan above.
 */
export function ApprovalScope({ proposal }: { proposal: TradeProposal }) {
  const base = baseSymbol(proposal.symbol);
  const scope = [
    `${proposal.side === 'buy' ? 'Buy' : 'Sell'} ${proposal.quantity} ${base} at ${
      proposal.order_type === 'limit'
        ? `a limit of ${formatUsd(entryPrice(proposal), { cents: true })}`
        : 'the market price'
    }, at ${proposal.leverage}× leverage.`,
    `A stop at ${formatUsd(Number(proposal.stop_loss), { cents: true })} and a target at ${formatUsd(
      Number(proposal.take_profit),
      { cents: true },
    )}, placed with the order.`,
    `These exact terms only, until ${formatClock(proposal.expires_at)}. Any change requires a new proposal.`,
    'Market and account checks run again before submission. A failed check blocks the order.',
    'This approval cannot withdraw, transfer, or move funds anywhere.',
  ];

  return (
    <View style={styles.block}>
      {scope.map((line) => (
        <View key={line} style={styles.line}>
          <Glyph
            color={tokens.color.text.tertiary}
            name="checkmark"
            size={13}
            style={styles.mark}
          />
          <Text style={styles.text} tone="secondary" variant="callout">
            {line}
          </Text>
        </View>
      ))}
      <Text numeric selectable style={styles.hash} tone="tertiary" variant="caption">
        Reference {proposal.proposal_hash.slice(0, 12)}…{proposal.proposal_hash.slice(-8)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: tokens.space.md, marginTop: tokens.space.base },
  line: { flexDirection: 'row', gap: tokens.space.md },
  mark: { marginTop: 3 },
  text: { flex: 1 },
  hash: { marginTop: tokens.space.xs },
});
