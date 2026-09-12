import { useState } from 'react';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { RefreshControl, View } from 'react-native';
import { tokens } from '@/theme/tokens';
import {
  Button,
  Card,
  CardRow,
  ErrorState,
  LoadingBlock,
  Screen,
  Section,
  Text,
} from '@/components/ui';
import { ExecutionActionPanel } from '@/components/proposal/ExecutionActionPanel';
import { environmentName } from '@/domain/connection';
import { getStudioApi } from '@/services/api';
import { studioKeys } from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { formatRelativeIso, formatSignedUsd, formatUsd } from '@/lib/format';

export default function PositionScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const owner = useAppStore((state) => state.ownerUserId);
  const [action, setAction] = useState<'close_position' | 'update_protection' | null>(null);
  const query = useQuery({
    queryKey: [...studioKeys.positions(), owner, 'detail', id],
    queryFn: () => getStudioApi().getPosition(id),
    enabled: Boolean(owner && id),
  });
  const position = query.data;
  return (
    <>
      <Stack.Screen options={{ title: position?.symbol ?? 'Position' }} />
      <Screen
        refreshControl={
          <RefreshControl refreshing={query.isRefetching} onRefresh={() => void query.refetch()} />
        }
      >
        {query.isLoading ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorState onRetry={() => void query.refetch()} />
        ) : position ? (
          <>
            <Text variant="footnote" tone="secondary">
              Bybit · {environmentName(position.environment)} ·{' '}
              {position.state === 'open' ? 'Open' : 'Closed'}
            </Text>
            <Section
              title={`${position.side === 'buy' ? 'Long' : 'Short'} ${position.symbol}`}
              level="primary"
              caption={`Reconciled ${formatRelativeIso(position.last_reconciled_at)}`}
            >
              <Card style={{ marginTop: tokens.space.base }}>
                <CardRow label="Size" value={position.size} />
                <CardRow
                  label="Exposure"
                  value={formatUsd(Number(position.position_value), { cents: true })}
                />
                <CardRow label="Entry price" value={position.average_price} />
                <CardRow label="Mark price" value={position.mark_price} />
                <CardRow
                  label="Unrealised P&L"
                  value={formatSignedUsd(Number(position.unrealised_pnl))}
                />
                <CardRow
                  label="Leverage"
                  value={position.leverage ? `${position.leverage}×` : '—'}
                />
                <CardRow
                  label="Broker stop loss"
                  value={Number(position.stop_loss) > 0 ? position.stop_loss! : 'Not set'}
                />
                <CardRow
                  label="Broker take profit"
                  value={Number(position.take_profit) > 0 ? position.take_profit! : 'Not set'}
                  last
                />
              </Card>
            </Section>
            {action ? (
              <ExecutionActionPanel key={`${id}:${action}`} type={action} targetId={id} />
            ) : position.state === 'open' ? (
              <Section title="Manage position">
                <View style={{ gap: tokens.space.base, marginTop: tokens.space.base }}>
                  <Button
                    title="Update stop / target"
                    variant="secondary"
                    onPress={() => setAction('update_protection')}
                  />
                  <Button
                    title="Close position"
                    variant="destructive"
                    onPress={() => setAction('close_position')}
                  />
                </View>
              </Section>
            ) : null}
          </>
        ) : null}
      </Screen>
    </>
  );
}
