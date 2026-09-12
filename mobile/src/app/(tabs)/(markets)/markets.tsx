import { useCallback, useMemo, useState } from 'react';
import { Stack, router } from 'expo-router';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { MarketColumns, MarketRow } from '@/components/markets/MarketRow';
import {
  Button,
  EmptyState,
  ErrorState,
  LoadingBlock,
  Segmented,
  Text,
  useToast,
} from '@/components/ui';
import type { MarketCandidate, MarketCategory } from '@/domain/studio';
import { useLatestMarketScan, useRunMarketScan } from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { formatClock } from '@/lib/format';
import { tokens } from '@/theme/tokens';

type CategoryFilter = 'all' | MarketCategory;

const filters = [
  { value: 'all' as const, label: 'All' },
  { value: 'linear' as const, label: 'Perpetuals' },
  { value: 'spot' as const, label: 'Spot' },
];

export default function MarketsScreen() {
  const environment = useAppStore((state) => state.brokerEnvironment);
  const scan = useLatestMarketScan(environment);
  const runMarketScan = useRunMarketScan(environment);
  const { showToast } = useToast();
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<CategoryFilter>('all');
  const [refreshing, setRefreshing] = useState(false);

  const startScan = useCallback(async () => {
    try {
      const next = await runMarketScan.mutateAsync();
      showToast({
        title: 'Market universe updated',
        message: `${next.result.hot_universe.length} liquid markets. Proposals appear only after all checks pass.`,
        tone: 'success',
      });
    } catch {
      showToast({
        title: 'Market scan did not complete',
        message: 'Bybit market data was unavailable. Try again in a moment.',
        tone: 'error',
      });
    }
  }, [runMarketScan, showToast]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await scan.refetch();
    } finally {
      setRefreshing(false);
    }
  }, [scan]);

  const candidates = useMemo(() => {
    const search = query.trim().toLowerCase();
    return (scan.data?.result.hot_universe ?? []).filter(
      (candidate) =>
        (category === 'all' || candidate.category === category) &&
        candidate.symbol.toLowerCase().includes(search),
    );
  }, [category, query, scan.data]);

  const renderItem = useCallback(
    ({ item }: { item: MarketCandidate }) => (
      <MarketRow
        candidate={item}
        onPress={() =>
          router.push({
            pathname: '/market/[symbol]',
            params: { symbol: item.symbol, category: item.category },
          })
        }
      />
    ),
    [],
  );

  return (
    <>
      <Stack.Screen
        options={{
          headerSearchBarOptions: {
            placeholder: 'Search markets',
            onChangeText: (event) => setQuery(event.nativeEvent.text),
            onCancelButtonPress: () => setQuery(''),
            hideWhenScrolling: false,
            placement: 'stacked',
            allowToolbarIntegration: false,
          },
        }}
      />
      <FlatList
        ListEmptyComponent={
          scan.isLoading ? (
            <LoadingBlock />
          ) : scan.isError ? (
            <ErrorState onRetry={() => void scan.refetch()} retrying={scan.isRefetching} />
          ) : (
            <EmptyState
              align="center"
              body={
                query || category !== 'all'
                  ? 'No market in the current liquid universe matches this filter.'
                  : 'Discover liquid Bybit markets. Personalized reviews live in Studio.'
              }
              action={
                query || category !== 'all'
                  ? undefined
                  : {
                      title: 'Scan markets',
                      icon: 'magnifyingglass',
                      onPress: () => void startScan(),
                      loading: runMarketScan.isPending,
                      variant: 'primary',
                    }
              }
              symbol={query || category !== 'all' ? 'magnifyingglass' : 'chart.xyaxis.line'}
              title={query || category !== 'all' ? 'No matching markets' : 'Explore the market'}
            />
          )
        }
        ListHeaderComponent={
          scan.data ? (
            <View style={styles.header}>
              <View style={styles.scanSummary}>
                <Text style={styles.summaryCopy} tone="secondary" variant="callout">
                  {`${scan.data.result.hot_universe.length} liquid · ${formatClock(scan.data.observed_at)}`}
                </Text>
                <Button
                  title="Scan"
                  size="compact"
                  loading={runMarketScan.isPending}
                  onPress={() => void startScan()}
                  icon="arrow.clockwise"
                />
              </View>
              <Segmented
                label="Market category"
                onChange={setCategory}
                options={filters}
                value={category}
              />
              {candidates.length ? <MarketColumns /> : null}
            </View>
          ) : null
        }
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        data={candidates}
        keyboardDismissMode="on-drag"
        keyExtractor={(item) => `${item.category}-${item.symbol}`}
        refreshControl={
          <RefreshControl
            onRefresh={() => void refresh()}
            refreshing={refreshing}
            tintColor={tokens.color.text.tertiary}
          />
        }
        renderItem={renderItem}
        style={styles.list}
        windowSize={7}
      />
    </>
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, backgroundColor: tokens.color.bg.canvas },
  content: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.md,
    paddingBottom: tokens.space.section + tokens.layout.tabBarClearance,
  },
  header: { gap: tokens.space.lg, paddingBottom: tokens.space.sm },
  scanSummary: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.space.md,
  },
  summaryCopy: { flex: 1 },
});
