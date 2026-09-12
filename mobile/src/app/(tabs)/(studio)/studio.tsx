import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Stack, router } from 'expo-router';
import { RefreshControl, StyleSheet, View } from 'react-native';
import { useAnimatedScrollHandler, useSharedValue } from 'react-native-reanimated';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { SignalRow } from '@/components/signals/SignalRow';
import { ConnectionAlert } from '@/components/studio/ConnectionAlert';
import { PortfolioBrief } from '@/components/studio/PortfolioBrief';
import { MarketReviewList } from '@/components/studio/MarketReviewList';
import { StudioTitle } from '@/components/studio/StudioTitle';
import {
  Avatar,
  Card,
  CardRow,
  EmptyState,
  ErrorState,
  LoadingBlock,
  Reveal,
  Screen,
  Section,
  useToast,
} from '@/components/ui';
import { connectionHealth } from '@/domain/connection';
import { proposalEmptyState } from '@/domain/marketReview';
import { isAwaitingDecision, isSubmitted } from '@/domain/proposal';
import type { MarketReviewCandidate } from '@/domain/studio';
import { formatRelativeTime, formatUsd } from '@/lib/format';
import { useNow } from '@/lib/useNow';
import {
  useOpenPositions,
  useLatestMarketReview,
  useMarketAnalysisRequest,
  usePortfolioSummary,
  useRequestMarketAnalysis,
  useSyncBrokerConnection,
  useTradeProposals,
} from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

/** How many proposals the brief shows before deferring to the Signals tab. */
const PREVIEW_LIMIT = 2;
export default function StudioScreen() {
  // A minute is fine: everything on this screen is stated in minutes or hours.
  const now = useNow(60_000);
  const account = useAppStore((state) => state.account);
  const connection = useAppStore((state) => state.brokerConnection);
  const equityHistory = useAppStore((state) => state.equityHistory);

  const portfolio = usePortfolioSummary();
  const positions = useOpenPositions();
  const syncBroker = useSyncBrokerConnection();
  const proposals = useTradeProposals();
  const environment = connection?.environment ?? 'mainnet';
  const marketReview = useLatestMarketReview(environment);
  const requestMarketAnalysis = useRequestMarketAnalysis(environment);
  const { showToast } = useToast();
  const [requestedAnalysis, setRequestedAnalysis] = useState<{
    id: string;
    connectionId: string | undefined;
  } | null>(null);
  const analysisRequestId =
    requestedAnalysis?.connectionId === connection?.id ? (requestedAnalysis?.id ?? null) : null;
  const analysisRequest = useMarketAnalysisRequest(analysisRequestId);
  const analysisActive =
    analysisRequest.data?.status === 'queued' || analysisRequest.data?.status === 'running';
  const analysisDelayed = Boolean(
    analysisActive &&
    analysisRequest.data &&
    now.getTime() -
      new Date(analysisRequest.data.started_at ?? analysisRequest.data.requested_at).getTime() >
      120_000,
  );
  const handledAnalysisRequest = useRef<string | null>(null);

  const health = connectionHealth(connection);
  const healthy = connection?.status === 'healthy';
  const awaiting = useMemo(
    () => (proposals.data ?? []).filter(isAwaitingDecision),
    [proposals.data],
  );
  const submitted = useMemo(() => (proposals.data ?? []).filter(isSubmitted), [proposals.data]);
  const emptyProposals = proposalEmptyState(marketReview.data ?? undefined);

  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    const request = analysisRequest.data;
    if (!request || handledAnalysisRequest.current === request.id) return;
    if (request.status === 'completed') {
      handledAnalysisRequest.current = request.id;
      void Promise.all([marketReview.refetch(), proposals.refetch()]).then(() => {
        showToast({
          title: 'Market review complete',
          message: 'The latest decisions and any new proposals are ready.',
          tone: 'success',
        });
      });
    } else if (request.status === 'failed') {
      handledAnalysisRequest.current = request.id;
      showToast({
        title: 'Market review did not complete',
        message: 'The review did not finish. Refresh to see any results saved before it stopped.',
        tone: 'error',
      });
    }
  }, [analysisRequest.data, marketReview, proposals, showToast]);

  const startMarketReview = useCallback(async () => {
    if (analysisActive || analysisRequest.isError) {
      void analysisRequest.refetch();
      return;
    }
    if (requestMarketAnalysis.isPending) return;
    try {
      const request = await requestMarketAnalysis.mutateAsync();
      handledAnalysisRequest.current = null;
      setRequestedAnalysis({ id: request.id, connectionId: connection?.id });
      showToast({
        title: request.status === 'queued' ? 'Review queued' : 'Review started',
        message:
          request.status === 'queued'
            ? 'Waiting for the market worker.'
            : 'Checking fresh market data and approved strategies.',
        tone: 'info',
      });
    } catch {
      showToast({
        title: 'Could not start review',
        message: 'Nothing changed. Check the backend connection and try again.',
        tone: 'error',
      });
    }
  }, [analysisActive, analysisRequest, connection, requestMarketAnalysis, showToast]);

  const syncPortfolio = useCallback(
    async (announce = false) => {
      if (!healthy || !connection || syncBroker.isPending) return;
      try {
        await syncBroker.mutateAsync(connection.id);
        if (announce)
          showToast({
            title: 'Portfolio synced',
            message: 'Your latest Bybit balances are now shown.',
            tone: 'success',
          });
      } catch {
        if (announce)
          showToast({
            title: 'Sync needs attention',
            message:
              'The saved portfolio is still shown. Check your Bybit connection and try again.',
            tone: 'error',
          });
      }
    },
    [connection, healthy, showToast, syncBroker],
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await syncPortfolio();
      await Promise.all([
        portfolio.refetch(),
        positions.refetch(),
        proposals.refetch(),
        marketReview.refetch(),
      ]);
    } finally {
      setRefreshing(false);
    }
  }, [marketReview, portfolio, positions, proposals, syncPortfolio]);

  const scrollY = useSharedValue(0);
  const onScroll = useAnimatedScrollHandler((event) => {
    scrollY.value = event.contentOffset.y;
  });

  const openAccount = useCallback(() => router.navigate('/account'), []);
  const openProposal = useCallback(
    (id: string) => router.push({ pathname: '/trade-proposal/[id]', params: { id } }),
    [],
  );
  const openMarketReview = useCallback(
    (candidate: MarketReviewCandidate) =>
      router.push({
        pathname: '/market-review/[symbol]',
        params: { category: candidate.category, symbol: candidate.symbol },
      }),
    [],
  );

  return (
    <>
      <Stack.Screen
        options={{
          // The lockup goes in the title slot, not headerLeft: iOS 26 wraps
          // header *items* in a glass capsule, which would make the wordmark
          // look like a button that does nothing when pressed.
          headerTitle: () => (
            <StudioTitle
              scrollY={scrollY}
              value={
                portfolio.data
                  ? formatUsd(Number(portfolio.data.total_equity), { cents: true })
                  : null
              }
            />
          ),
          headerRight: () => (
            <Avatar
              firstName={account.firstName}
              lastName={account.lastName}
              onPress={openAccount}
            />
          ),
        }}
      />
      <Screen
        onScroll={onScroll}
        refreshControl={
          <RefreshControl
            onRefresh={refresh}
            refreshing={refreshing}
            tintColor={tokens.color.text.tertiary}
          />
        }
      >
        <Reveal index={0}>
          <PortfolioBrief
            disconnected={!healthy}
            history={equityHistory}
            loading={portfolio.isLoading}
            now={now.getTime()}
            onSync={() => void syncPortfolio(true)}
            positions={positions.data ?? []}
            summary={portfolio.data}
            syncing={syncBroker.isPending}
          />
          {portfolio.data ? (
            <Card style={styles.holdings}>
              <CardRow
                emphasis
                label="Holdings & positions"
                detail="See where your funds are held"
                last
                onPress={() => router.push('/portfolio')}
              />
            </Card>
          ) : null}
        </Reveal>

        <Reveal index={1}>
          {health.needsAttention ? (
            <ConnectionAlert connection={connection} health={health} onPress={openAccount} />
          ) : null}
        </Reveal>

        <Reveal index={2}>
          {proposals.isLoading ? (
            <View style={styles.proposalsSkeleton}>
              <LoadingBlock lines={2} />
            </View>
          ) : (
            <Section
              action={
                awaiting.length ? (
                  <HeaderButton
                    label="See all"
                    onPress={() => router.navigate('/signals')}
                    showLabel
                  />
                ) : (
                  <HeaderButton
                    label="Markets"
                    onPress={() => router.navigate('/markets')}
                    showLabel
                  />
                )
              }
              count={awaiting.length}
              level="primary"
              title="Proposals"
            >
              {proposals.isError ? (
                <ErrorState
                  onRetry={() => void proposals.refetch()}
                  retrying={proposals.isRefetching}
                />
              ) : awaiting.length ? (
                <View style={styles.list}>
                  {awaiting.slice(0, PREVIEW_LIMIT).map((proposal) => (
                    <SignalRow
                      key={proposal.id}
                      now={now}
                      onPress={() => openProposal(proposal.id)}
                      portfolio={portfolio.data}
                      proposal={proposal}
                    />
                  ))}
                </View>
              ) : (
                <EmptyState
                  action={{
                    title:
                      analysisDelayed || analysisRequest.isError
                        ? 'Check review status'
                        : analysisActive
                          ? 'Review in progress'
                          : emptyProposals.actionTitle,
                    icon: 'arrow.clockwise',
                    loading:
                      requestMarketAnalysis.isPending || (analysisActive && !analysisDelayed),
                    onPress: () => void startMarketReview(),
                    variant: 'primary',
                  }}
                  align="center"
                  body={
                    analysisRequest.isError
                      ? 'Review status could not be loaded. Check status before starting another review.'
                      : analysisDelayed
                        ? 'This review is taking longer than expected. It remains queued or running; your last results are still available.'
                        : emptyProposals.body
                  }
                  density="compact"
                  symbol="doc.text.magnifyingglass"
                  title={emptyProposals.title}
                />
              )}
            </Section>
          )}
        </Reveal>

        {marketReview.data?.candidates.length ? (
          <Reveal index={3}>
            <Section
              action={
                <HeaderButton
                  label="Markets"
                  showLabel
                  onPress={() => router.navigate('/markets')}
                />
              }
              caption={`Reviewed ${formatRelativeTime(
                new Date(marketReview.data.analyzed_at).getTime(),
                now.getTime(),
              )}`}
              style={styles.reviewSection}
              title="Latest market review"
            >
              <MarketReviewList
                approvedStrategyCount={marketReview.data.approved_strategies}
                candidates={marketReview.data.candidates}
                onOpenReview={openMarketReview}
              />
            </Section>
          </Reveal>
        ) : null}

        {submitted.length ? (
          <Reveal index={4}>
            <Section
              action={
                <HeaderButton
                  label="See all"
                  onPress={() => router.navigate('/signals')}
                  showLabel
                />
              }
              title="Submitted proposals"
            >
              <View style={styles.list}>
                {submitted.slice(0, PREVIEW_LIMIT).map((proposal) => (
                  <SignalRow
                    key={proposal.id}
                    now={now}
                    portfolio={portfolio.data}
                    onPress={() => openProposal(proposal.id)}
                    proposal={proposal}
                  />
                ))}
              </View>
            </Section>
          </Reveal>
        ) : null}
      </Screen>
    </>
  );
}

const styles = StyleSheet.create({
  list: { marginTop: tokens.space.md },
  proposalsSkeleton: { marginTop: tokens.space.xl },
  reviewSection: { marginTop: tokens.space.lg },
  holdings: { marginTop: tokens.space.lg },
});
