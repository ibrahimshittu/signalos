import { StyleSheet, View } from 'react-native';
import { statusGlyph } from './statusGlyph';
import { StatusBadge, Glyph, Text } from '@/components/ui';
import {
  baseSymbol,
  directionLabel,
  expiryState,
  isAwaitingDecision,
  orderStatusPresentation,
  quoteSymbol,
  statusPresentation,
  strategyLabel,
} from '@/domain/proposal';
import type { BrokerOrderState, TradeProposal } from '@/domain/studio';
import { formatClock } from '@/lib/format';
import { tokens } from '@/theme/tokens';

/** What this is, which way it points, where it stands, and how long it lasts. */
export function ProposalHeadline({
  now,
  proposal,
  orderState,
}: {
  proposal: TradeProposal;
  now: Date;
  orderState?: BrokerOrderState;
}) {
  const status = orderState
    ? orderStatusPresentation(orderState)
    : statusPresentation(proposal.status);
  const expiry = expiryState(proposal, now);
  const long = proposal.side === 'buy';
  const tint = long ? tokens.color.finance.gain : tokens.color.finance.loss;

  return (
    <View style={styles.block}>
      <Text tone="secondary" variant="subhead">
        {strategyLabel(proposal.strategy_family)} ·{' '}
        {proposal.category === 'linear' ? 'Perpetual' : 'Spot'}
        {/* A live account is the default; only a test account needs saying. */}
        {proposal.environment === 'testnet' ? ' · Testnet' : ''}
      </Text>

      <View style={styles.instrument}>
        <Text variant="display">
          {baseSymbol(proposal.symbol)}
          <Text tone="tertiary" variant="title2">
            {' / '}
            {quoteSymbol(proposal.symbol)}
          </Text>
        </Text>
        <View style={styles.direction}>
          <Glyph color={tint} name={long ? 'arrow.up.right' : 'arrow.down.right'} size={15} />
          <Text style={{ color: tint }} variant="title3">
            {directionLabel(proposal.side)}
          </Text>
        </View>
      </View>

      <View style={styles.status}>
        <StatusBadge
          label={status.label}
          symbol={orderState ? 'paperplane' : statusGlyph(proposal.status)}
          tone={status.tone}
        />
        {isAwaitingDecision(proposal) && !orderState ? (
          <Text tone={expiry.state === 'open' ? 'tertiary' : 'caution'} variant="caption">
            {expiry.label} · until {formatClock(proposal.expires_at)}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: tokens.space.sm },
  instrument: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: tokens.space.md,
  },
  direction: { flexDirection: 'row', alignItems: 'center', gap: tokens.space.xs },
  status: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: tokens.space.md,
    marginTop: tokens.space.xs,
  },
});
