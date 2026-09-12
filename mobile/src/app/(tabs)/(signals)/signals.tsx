import { useCallback, useMemo, useState } from 'react';
import { router, Stack } from 'expo-router';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { SignalRow } from '@/components/signals/SignalRow';
import { EmptyState, ErrorState, LoadingBlock, Segmented, Text } from '@/components/ui';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { proposalPhase, type ProposalPhase } from '@/domain/proposal';
import type { TradeProposal } from '@/domain/studio';
import { useNow } from '@/lib/useNow';
import { usePortfolioSummary, useTradeProposals } from '@/query/studioHooks';
import { tokens } from '@/theme/tokens';

/**
 * The awaiting segment carries its count, because that number is what the tab
 * badge shows. Without it the badge is a bare digit with nothing on the
 * destination screen to explain what it counted.
 */
function buildFilters(awaiting: number) {
  return [
    { value: 'awaiting' as const, label: awaiting > 0 ? `Awaiting · ${awaiting}` : 'Awaiting' },
    { value: 'submitted' as const, label: 'Submitted' },
    { value: 'closed' as const, label: 'History' },
  ];
}

const copy: Record<ProposalPhase, { lede: string; title: string; body: string }> = {
  awaiting: {
    lede: 'Your proposals, with the case and risk laid out.',
    title: 'You’re up to date',
    body: 'No proposals need your decision.',
  },
  submitted: {
    lede: 'Track orders you approved. Submission is not a fill.',
    title: 'No submitted proposals',
    body: 'Proposals appear here after you confirm their order review.',
  },
  closed: {
    lede: 'Past proposals and the reasoning behind them.',
    title: 'No history yet',
    body: 'Expired, declined, and archived proposals appear here.',
  },
};

export default function SignalsScreen() {
  const now = useNow(60_000);
  const [filter, setFilter] = useState<ProposalPhase>('awaiting');
  const proposals = useTradeProposals();
  const portfolio = usePortfolioSummary();
  const [refreshing, setRefreshing] = useState(false);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([proposals.refetch(), portfolio.refetch()]);
    } finally {
      setRefreshing(false);
    }
  }, [portfolio, proposals]);

  const visible = useMemo(
    () => (proposals.data ?? []).filter((proposal) => proposalPhase(proposal) === filter),
    [filter, proposals.data],
  );

  const filters = useMemo(
    () =>
      buildFilters(
        (proposals.data ?? []).filter((proposal) => proposalPhase(proposal) === 'awaiting').length,
      ),
    [proposals.data],
  );

  const open = useCallback(
    (id: string) => router.push({ pathname: '/trade-proposal/[id]', params: { id } }),
    [],
  );

  const renderItem = useCallback(
    ({ item }: { item: TradeProposal }) => (
      <SignalRow
        now={now}
        onPress={() => open(item.id)}
        portfolio={portfolio.data}
        proposal={item}
      />
    ),
    [now, open, portfolio.data],
  );

  return (
    <>
      <Stack.Screen
        options={{
          headerRight: () => (
            <HeaderButton label="Positions" showLabel onPress={() => router.push('/portfolio')} />
          ),
        }}
      />
      <FlatList
        ListEmptyComponent={
          proposals.isLoading ? (
            <LoadingBlock />
          ) : proposals.isError ? (
            <ErrorState
              onRetry={() => void proposals.refetch()}
              retrying={proposals.isRefetching}
            />
          ) : (
            <EmptyState
              align="center"
              symbol={
                filter === 'awaiting'
                  ? 'tray'
                  : filter === 'submitted'
                    ? 'paperplane'
                    : 'clock.arrow.circlepath'
              }
              body={copy[filter].body}
              title={copy[filter].title}
            />
          )
        }
        ListHeaderComponent={
          <View style={styles.header}>
            <Segmented
              label="Proposal phase"
              onChange={setFilter}
              options={filters}
              value={filter}
            />
            <Text tone="secondary" variant="footnote">
              {copy[filter].lede}
            </Text>
          </View>
        }
        contentContainerStyle={styles.content}
        contentInsetAdjustmentBehavior="automatic"
        data={visible}
        keyExtractor={(item) => item.id}
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
  header: { gap: tokens.space.lg, paddingBottom: tokens.space.base },
});
