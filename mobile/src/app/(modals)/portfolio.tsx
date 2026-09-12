import { router, Stack } from 'expo-router';
import { RefreshControl } from 'react-native';
import {
  Button,
  Card,
  CardRow,
  EmptyState,
  ErrorState,
  LoadingBlock,
  Screen,
  Section,
  Text,
} from '@/components/ui';
import { PositionBreakdown } from '@/components/studio/PositionBreakdown';
import { environmentName } from '@/domain/connection';
import {
  useOpenPositions,
  usePortfolioSummary,
  useSyncBrokerConnection,
} from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { formatRelativeIso, formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

export default function PortfolioScreen() {
  const portfolio = usePortfolioSummary();
  const positions = useOpenPositions();
  const sync = useSyncBrokerConnection();
  const connection = useAppStore((state) => state.brokerConnection);
  const summary = portfolio.data;
  const holdings =
    summary?.balances.filter(
      (balance) => Number(balance.equity) !== 0 || Number(balance.wallet_balance) !== 0,
    ) ?? [];
  return (
    <>
      <Stack.Screen options={{ title: 'Holdings & positions' }} />
      <Screen
        refreshControl={
          <RefreshControl
            refreshing={positions.isRefetching}
            onRefresh={() => {
              void positions.refetch();
              void portfolio.refetch();
            }}
          />
        }
      >
        {portfolio.isLoading ? (
          <LoadingBlock />
        ) : portfolio.isError ? (
          <ErrorState onRetry={() => void portfolio.refetch()} />
        ) : summary ? (
          <>
            <Text variant="footnote" tone="secondary">
              Bybit · {environmentName(summary.environment)} ·{' '}
              {formatRelativeIso(summary.captured_at)}
            </Text>
            <Section title="Account balances" level="primary">
              <Card style={{ marginTop: tokens.space.base }}>
                <CardRow
                  label="Total equity"
                  value={formatUsd(Number(summary.total_equity), { cents: true })}
                />
                <CardRow
                  label="Available balance"
                  value={formatUsd(Number(summary.available_balance), { cents: true })}
                  last
                />
              </Card>
              <Button
                title="Refresh balances from Bybit"
                style={{ marginTop: tokens.space.base }}
                size="compact"
                variant="secondary"
                loading={sync.isPending}
                onPress={() => {
                  if (connection) sync.mutate(connection.id);
                }}
              />
              {sync.isError ? (
                <Text tone="loss">
                  Balances could not be refreshed. The last snapshot is shown.
                </Text>
              ) : null}
            </Section>
            <Section
              title="Wallet holdings"
              caption="Native coin units, not dollar values or available trading margin."
            >
              {holdings.length ? (
                <Card style={{ marginTop: tokens.space.base }}>
                  {holdings.map((balance, index) => (
                    <CardRow
                      key={balance.coin}
                      label={balance.coin}
                      value={balance.wallet_balance}
                      detail={`Equity: ${balance.equity} ${balance.coin}`}
                      last={index === holdings.length - 1}
                    />
                  ))}
                </Card>
              ) : (
                <Text tone="secondary">No non-zero wallet holdings in this snapshot.</Text>
              )}
            </Section>
          </>
        ) : (
          <EmptyState
            title="No account snapshot"
            body="Connect and sync a provider to see your holdings."
            action={{ title: 'Connect provider', onPress: () => router.push('/connect') }}
          />
        )}
        <Section
          title="Open positions"
          caption="Broker-reconciled positions. Values below are exposure, not allocated cash."
        >
          {positions.isLoading ? (
            <LoadingBlock />
          ) : positions.isError ? (
            <ErrorState onRetry={() => void positions.refetch()} />
          ) : positions.data?.length ? (
            <PositionBreakdown positions={positions.data} />
          ) : (
            <Text tone="secondary">No open positions in the latest reconciliation.</Text>
          )}
        </Section>
      </Screen>
    </>
  );
}
