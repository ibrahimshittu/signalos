import { memo } from 'react';
import { StyleSheet, View } from 'react-native';
import { Glyph, StatusBadge, Text, Touchable } from '@/components/ui';
import type { GlyphName, StatusTone } from '@/components/ui';
import type { MarketReviewCandidate, MarketReviewStatus } from '@/domain/studio';
import { tokens } from '@/theme/tokens';

const statusPresentation: Record<
  MarketReviewStatus,
  { label: string; tone: StatusTone; symbol: GlyphName }
> = {
  model_unavailable: {
    label: 'Analysis paused',
    tone: 'caution',
    symbol: 'exclamationmark.triangle.fill',
  },
  market_data_unavailable: {
    label: 'Data unavailable',
    tone: 'caution',
    symbol: 'wifi.exclamationmark',
  },
  no_approved_strategy: {
    label: 'No strategy fit',
    tone: 'neutral',
    symbol: 'minus.circle',
  },
  no_strategy_match: {
    label: 'No strategy fit',
    tone: 'neutral',
    symbol: 'minus.circle',
  },
  evidence_gate_rejected: {
    label: 'Evidence blocked',
    tone: 'caution',
    symbol: 'exclamationmark.triangle.fill',
  },
  no_valid_signal: { label: 'No valid setup', tone: 'neutral', symbol: 'minus.circle' },
  ai_no_trade: { label: 'No-trade decision', tone: 'active', symbol: 'hand.raised.fill' },
  passed_market_checks: {
    label: 'Passed market checks',
    tone: 'active',
    symbol: 'checkmark.circle.fill',
  },
};

const categoryLabel = { linear: 'Perpetual', spot: 'Spot' } as const;

function splitSymbol(symbol: string): [string, string] {
  if (symbol.endsWith('USDT')) return [symbol.slice(0, -4), 'USDT'];
  return [symbol, ''];
}

interface Props {
  approvedStrategyCount: number;
  candidates: MarketReviewCandidate[];
  onOpenReview(candidate: MarketReviewCandidate): void;
}

const screenedPresentation = {
  label: 'Screened',
  tone: 'neutral' as const,
  symbol: 'checkmark.circle.fill' as const,
};

export const MarketReviewList = memo(function MarketReviewList({
  approvedStrategyCount,
  candidates,
  onOpenReview,
}: Props) {
  return (
    <View style={styles.list}>
      {candidates.map((candidate) => {
        const [base, quote] = splitSymbol(candidate.symbol);
        const catalogUnavailable =
          candidate.status === 'no_approved_strategy' && approvedStrategyCount === 0;
        const portfolioBlocked =
          candidate.portfolio_review &&
          !['proposed', 'already_proposed'].includes(candidate.portfolio_review.code);
        const status = portfolioBlocked
          ? { label: 'Portfolio check', tone: 'caution' as const, symbol: 'info.circle' as const }
          : catalogUnavailable
            ? screenedPresentation
            : statusPresentation[candidate.status];
        return (
          <Touchable
            accessibilityHint="Shows where this candidate stopped and which checks did not run"
            accessibilityLabel={`Open ${base}${quote ? `/${quote}` : ''} review details`}
            accessibilityRole="button"
            feedback="highlight"
            key={`${candidate.category}:${candidate.symbol}`}
            onPress={() => onOpenReview(candidate)}
            style={styles.row}
          >
            <View style={styles.body}>
              <View style={styles.heading}>
                <View style={styles.identity}>
                  <Text variant="headline">
                    {base}
                    {quote ? (
                      <Text tone="tertiary" variant="subhead">
                        {' / '}
                        {quote}
                      </Text>
                    ) : null}
                  </Text>
                  <Text numeric tone="tertiary" variant="caption">
                    #{candidate.rank} · {categoryLabel[candidate.category]}
                  </Text>
                </View>
                <StatusBadge label={status.label} symbol={status.symbol} tone={status.tone} />
              </View>
              {catalogUnavailable ? null : (
                <Text style={styles.reason} tone="secondary" variant="footnote">
                  {candidate.portfolio_review?.reason ?? candidate.reason}
                </Text>
              )}
            </View>
            <Glyph
              color={tokens.color.text.tertiary}
              name="chevron.right"
              size={12}
              style={styles.chevron}
            />
          </Touchable>
        );
      })}
    </View>
  );
});

const styles = StyleSheet.create({
  list: { marginTop: tokens.space.md },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: tokens.space.md,
    paddingHorizontal: tokens.space.sm,
    marginHorizontal: -tokens.space.sm,
    paddingVertical: tokens.space.base,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: tokens.color.border.hairline,
  },
  body: { flex: 1 },
  heading: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: tokens.space.md,
  },
  identity: { flexGrow: 1, flexBasis: 120, gap: tokens.optical.nudge },
  reason: { marginTop: tokens.space.sm, maxWidth: 520 },
  chevron: { marginTop: tokens.optical.nudge },
});
