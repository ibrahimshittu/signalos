import { useMemo } from 'react';
import { Stack, router, useLocalSearchParams } from 'expo-router';
import { ScrollView, StyleSheet, View } from 'react-native';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { Card, CardRow, EmptyState, Glyph, Meter, Tag, Text } from '@/components/ui';
import { baseSymbol, quoteSymbol } from '@/domain/proposal';
import { useLatestMarketScan } from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { formatClock, formatCompactUsd, formatSignedRatioPct } from '@/lib/format';
import { colorForChange, tokens } from '@/theme/tokens';

/**
 * A single scanned market, in a sheet.
 *
 * Built on the same spine as the trade proposal — a quiet meta line, the
 * instrument at display size, then the figure that matters, then grouped
 * detail — so opening either one feels like the same product.
 *
 * It is a read-only reading of the scan, not a trading screen: no buy control,
 * no chart to scrub, no order entry. SignalOS proposes trades from its own
 * analysis, and a market row that looked like a way to start one would blur
 * the line the whole product is built on.
 */
export default function MarketSheet() {
  const { symbol, category } = useLocalSearchParams<{ symbol: string; category?: string }>();
  const environment = useAppStore((state) => state.brokerEnvironment);
  const scan = useLatestMarketScan(environment);

  const candidate = useMemo(
    () =>
      scan.data?.result.hot_universe.find(
        (item) => item.symbol === symbol && item.category === category,
      ),
    [category, scan.data, symbol],
  );

  const close = () => (router.canGoBack() ? router.back() : router.replace('/markets'));
  // The instrument is the sheet's own headline; the bar stays generic so the
  // same fact is not stated twice within forty points.
  const screen = (
    <Stack.Screen
      options={{
        headerLeft: () => <HeaderButton label="Close" onPress={close} symbol="xmark" />,
        title: 'Market',
      }}
    />
  );

  if (!candidate) {
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
            body="This market left the liquid universe, or the scan refreshed while the sheet was open."
            symbol="magnifyingglass"
            title="No longer in the scan"
          />
        </ScrollView>
      </>
    );
  }

  const change = Number(candidate.price_change_24h);
  const activity = Math.round(Number(candidate.activity_score) * 100);
  const tint = colorForChange(change);

  return (
    <>
      {screen}
      <ScrollView
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        style={styles.sheet}
      >
        <Text tone="secondary" variant="subhead">
          {candidate.category === 'linear' ? 'Perpetual' : 'Spot'} · Liquid universe
        </Text>

        <View style={styles.instrument}>
          <Text variant="display">
            {baseSymbol(candidate.symbol)}
            <Text tone="tertiary" variant="title2">
              {' / '}
              {quoteSymbol(candidate.symbol)}
            </Text>
          </Text>
        </View>

        <View style={styles.change}>
          <Glyph
            color={tint}
            name={change > 0 ? 'arrow.up.right' : change < 0 ? 'arrow.down.right' : 'minus'}
            size={16}
          />
          <Text fit numeric style={{ color: tint }} variant="title1">
            {formatSignedRatioPct(change)}
          </Text>
          <Text tone="tertiary" variant="subhead">
            over 24 hours
          </Text>
        </View>

        <Card style={styles.card}>
          <CardRow
            detail="Traded value over the last 24 hours"
            label="Turnover"
            value={formatCompactUsd(Number(candidate.turnover_24h))}
          />
          <CardRow detail="Rank within the current scan" label="Activity">
            <View style={styles.activity}>
              <Text numeric variant="subhead">
                {activity}
              </Text>
              <Meter tint={tokens.color.accent.base} value={activity / 100} width={56} />
            </View>
          </CardRow>
          <CardRow
            detail="Between the best bid and ask"
            label="Spread"
            value={`${Number(candidate.spread_bps).toFixed(1)} bps`}
          />
          <CardRow
            label="Observed"
            last
            numeric={false}
            value={formatClock(candidate.observed_at)}
          />
        </Card>

        <View style={styles.note}>
          <Tag label="Read only" />
          <Text style={styles.noteText} tone="secondary" variant="footnote">
            This universe is built from liquidity and activity before any model sees it. Appearing
            here is not a recommendation, and nothing on this screen can start a trade.
          </Text>
        </View>
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  sheet: { flex: 1, backgroundColor: tokens.color.bg.canvas },
  content: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.sm,
    paddingBottom: tokens.space.xxxl,
  },
  instrument: { marginTop: tokens.space.sm },
  change: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: tokens.space.sm,
    marginTop: tokens.space.md,
  },
  card: { marginTop: tokens.space.xl },
  activity: { flexDirection: 'row', alignItems: 'center', gap: tokens.space.md },
  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: tokens.space.md,
    marginTop: tokens.space.lg,
  },
  noteText: { flex: 1 },
});
