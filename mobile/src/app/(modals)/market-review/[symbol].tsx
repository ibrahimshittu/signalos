import { useMemo } from 'react';
import { Stack, router, useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import {
  EmptyState,
  ErrorState,
  Glyph,
  LoadingBlock,
  Section,
  StatusBadge,
  Text,
} from '@/components/ui';
import type { GlyphName } from '@/components/ui';
import { explainMarketReview, type ReviewStepState } from '@/domain/marketReview';
import { baseSymbol, quoteSymbol } from '@/domain/proposal';
import type { MarketCategory } from '@/domain/studio';
import { formatRelativeTime } from '@/lib/format';
import { useNow } from '@/lib/useNow';
import { useLatestMarketReview } from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

const categoryLabel: Record<MarketCategory, string> = { linear: 'Perpetual', spot: 'Spot' };

const stepPresentation: Record<
  ReviewStepState,
  { color: string; label: string; symbol: GlyphName }
> = {
  passed: { color: tokens.color.accent.base, label: 'Passed', symbol: 'checkmark.circle.fill' },
  stopped: { color: tokens.color.status.caution, label: 'Stopped', symbol: 'stop.circle.fill' },
  unavailable: { color: tokens.color.accent.base, label: 'Unavailable', symbol: 'clock' },
  not_run: { color: tokens.color.text.tertiary, label: 'Not run', symbol: 'minus.circle' },
};

/** A stage-accurate explanation of one global market review candidate. */
export default function MarketReviewSheet() {
  const { category, symbol } = useLocalSearchParams<{
    category?: MarketCategory;
    symbol: string;
  }>();
  const environment = useAppStore((state) => state.brokerEnvironment);
  const review = useLatestMarketReview(environment);
  const now = useNow(60_000);

  const candidate = useMemo(
    () =>
      review.data?.candidates.find(
        (item) => item.symbol === symbol && (!category || item.category === category),
      ),
    [category, review.data, symbol],
  );
  const explanation = candidate
    ? explainMarketReview(candidate, review.data?.approved_strategies ?? 0)
    : null;
  const close = () => (router.canGoBack() ? router.back() : router.replace('/studio'));
  const screen = (
    <Stack.Screen
      options={{
        headerLeft: () => <HeaderButton label="Close" onPress={close} symbol="xmark" />,
        title: 'Market review',
      }}
    />
  );

  if (review.isLoading) {
    return (
      <>
        {screen}
        <ScrollView
          contentContainerStyle={styles.content}
          contentInsetAdjustmentBehavior="automatic"
          style={styles.sheet}
        >
          <LoadingBlock lines={4} />
        </ScrollView>
      </>
    );
  }

  if (review.isError) {
    return (
      <>
        {screen}
        <ScrollView
          contentContainerStyle={styles.content}
          contentInsetAdjustmentBehavior="automatic"
          style={styles.sheet}
        >
          <ErrorState onRetry={() => void review.refetch()} retrying={review.isRefetching} />
        </ScrollView>
      </>
    );
  }

  if (!candidate || !explanation || !review.data) {
    return (
      <>
        {screen}
        <ScrollView
          contentContainerStyle={styles.content}
          contentInsetAdjustmentBehavior="automatic"
          style={styles.sheet}
        >
          <EmptyState
            align="center"
            body="A newer deep review replaced this candidate. Return to Studio to open the latest decision."
            symbol="arrow.clockwise"
            title="Review updated"
          />
        </ScrollView>
      </>
    );
  }

  const passedReview = candidate.status === 'passed_market_checks';

  return (
    <>
      {screen}
      <ScrollView
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        style={styles.sheet}
      >
        <Text tone="secondary" variant="subhead">
          {categoryLabel[candidate.category]} · Reviewed{' '}
          {formatRelativeTime(new Date(review.data.analyzed_at).getTime(), now.getTime())}
        </Text>

        <View style={styles.instrument}>
          <Text variant="display">
            {baseSymbol(candidate.symbol)}
            <Text tone="tertiary" variant="title2">
              {' / '}
              {quoteSymbol(candidate.symbol)}
            </Text>
          </Text>
          <Text numeric tone="tertiary" variant="caption">
            Shortlist rank #{candidate.rank}
          </Text>
        </View>

        <View style={styles.decision}>
          <StatusBadge
            label={explanation.stage}
            tone={
              passedReview
                ? 'positive'
                : candidate.status === 'no_approved_strategy'
                  ? 'active'
                  : 'neutral'
            }
          />
          <Text accessibilityRole="header" style={styles.decisionTitle} variant="title1">
            {explanation.title}
          </Text>
          <Text tone="secondary" variant="body">
            {explanation.reason}
          </Text>
          {explanation.note ? (
            <View style={styles.note}>
              <Glyph color={tokens.color.text.tertiary} name="info.circle" size={16} />
              <Text style={styles.noteText} tone="secondary" variant="footnote">
                {explanation.note}
              </Text>
            </View>
          ) : null}
        </View>

        {candidate.portfolio_review ? (
          <Section
            title="For your account"
            caption={`Checked ${formatRelativeTime(new Date(candidate.portfolio_review.evaluated_at).getTime(), now.getTime())}`}
          >
            <Text style={styles.next} variant="callout">
              {candidate.portfolio_review.reason}
            </Text>
          </Section>
        ) : null}
        <Section level="secondary" title="Decision path">
          <View style={styles.steps}>
            {explanation.steps.map((step, index) => {
              const presentation = stepPresentation[step.state];
              return (
                <View key={`${step.label}:${index}`} style={styles.step}>
                  <Glyph
                    color={presentation.color}
                    name={presentation.symbol}
                    size={17}
                    style={styles.stepIcon}
                  />
                  <View style={styles.stepCopy}>
                    <View style={styles.stepHeading}>
                      <Text variant="subhead">{step.label}</Text>
                      <Text style={{ color: presentation.color }} variant="caption">
                        {presentation.label}
                      </Text>
                    </View>
                    <Text style={styles.stepDetail} tone="secondary" variant="footnote">
                      {step.detail}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>
        </Section>

        <Section level="secondary" title="Next">
          <Text style={styles.next} tone="secondary" variant="body">
            {explanation.next}
          </Text>
        </Section>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  sheet: { flex: 1, backgroundColor: tokens.color.bg.canvas },
  content: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.sm,
    paddingBottom: tokens.space.section,
  },
  instrument: { gap: tokens.space.xs, marginTop: tokens.space.sm },
  decision: { marginTop: tokens.space.xl },
  decisionTitle: { marginTop: tokens.space.md, marginBottom: tokens.space.sm },
  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: tokens.space.sm,
    marginTop: tokens.space.md,
  },
  noteText: { flex: 1, maxWidth: 560 },
  steps: { marginTop: tokens.space.sm },
  step: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: tokens.space.md,
    paddingVertical: tokens.space.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: tokens.color.border.hairline,
  },
  stepIcon: { marginTop: tokens.optical.nudge },
  stepCopy: { flex: 1 },
  stepHeading: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    gap: tokens.space.md,
  },
  stepDetail: { marginTop: tokens.space.xs },
  next: { marginTop: tokens.space.md, maxWidth: 560 },
});
