import { useRef, useState } from 'react';
import { View } from 'react-native';
import { tokens } from '@/theme/tokens';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Callout, Card, CardRow, Field, Section, Text } from '@/components/ui';
import type { ExecutionAction, ExecutionActionReview, ExecutionActionType } from '@/domain/studio';
import { environmentName } from '@/domain/connection';
import { formatUsd } from '@/lib/format';
import { getStudioApi } from '@/services/api';
import { SignalOSApiError } from '@/services/api/transport';
import { useAuthenticator } from '@/services/auth/useAuthenticator';
import { studioKeys } from '@/query/studioHooks';

const titles = {
  cancel_order: 'Cancel remaining order',
  close_position: 'Close position',
  update_protection: 'Update stop / target',
};

/** Existing reviewed-action API: authenticate, inspect fresh terms, then confirm. */
export function ExecutionActionPanel({
  type,
  targetId,
}: {
  type: ExecutionActionType;
  targetId: string;
}) {
  const auth = useAuthenticator();
  const client = useQueryClient();
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [stop, setStop] = useState('');
  const [target, setTarget] = useState('');
  const [review, setReview] = useState<ExecutionActionReview | null>(null);
  const [action, setAction] = useState<ExecutionAction | null>(null);
  const [attempted, setAttempted] = useState(false);
  const status = useQuery({
    queryKey: ['execution-action', action?.id],
    queryFn: () => getStudioApi().getExecutionAction(action!.id),
    enabled: Boolean(action),
    refetchInterval: (query) =>
      ['completed', 'rejected'].includes(query.state.data?.state ?? '') ? false : 5_000,
  });
  const outcome = status.data ?? action;

  async function run(work: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not prepare this action. Try again.',
      );
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  async function verify() {
    if (!(await auth.verify(code))) return;
    setCode('');
    const next = await getStudioApi().createExecutionReview(type, targetId, {
      ...(stop.trim() ? { stop_loss: stop.trim() } : {}),
      ...(target.trim() ? { take_profit: target.trim() } : {}),
    });
    if (next.terms.target_id !== targetId || next.terms.action_type !== type)
      throw new Error('The review does not match this action. Reopen it.');
    setReview(next);
  }

  async function confirm() {
    if (!review || attempted) return;
    if (new Date(review.expires_at).getTime() <= Date.now()) {
      setReview(null);
      throw new Error('This review expired. Review the latest terms again.');
    }
    setAttempted(true);
    try {
      setAction(
        await getStudioApi().confirmExecutionAction(type, targetId, {
          review_id: review.id,
          action_hash: review.action_hash,
          idempotency_key: `signalos-action:${review.action_hash}`,
        }),
      );
    } catch (cause) {
      if (cause instanceof SignalOSApiError && [401, 403, 404, 409, 422].includes(cause.status)) {
        setAttempted(false);
        setReview(null);
        throw cause;
      }
      throw new Error(
        'The outcome is not confirmed. Refresh the position or order before taking another action.',
      );
    } finally {
      void client.invalidateQueries({ queryKey: studioKeys.all });
    }
  }

  return (
    <Section title={titles[type]}>
      <View style={{ gap: tokens.space.base, marginTop: tokens.space.base }}>
        {error ? <Callout tone="caution" title="Action needs attention" body={error} /> : null}
        {status.isError ? (
          <Callout
            tone="caution"
            title="Confirmation unavailable"
            body="Could not refresh the broker action. Its outcome is still unknown; do not submit it again."
          />
        ) : null}
        {outcome ? (
          <Callout
            title={
              outcome.state === 'completed'
                ? 'Confirmed by Bybit'
                : outcome.state === 'rejected'
                  ? 'Bybit rejected this action'
                  : 'Awaiting broker confirmation'
            }
            body={
              outcome.state === 'completed'
                ? 'Refresh your position or order to see the updated state.'
                : outcome.state === 'rejected'
                  ? 'Nothing was confirmed. Refresh the latest record before trying again.'
                  : 'The reconciliation worker is checking the result. Acknowledgement is not a fill or a closed position.'
            }
          />
        ) : attempted ? null : review ? (
          <>
            <Card>
              <CardRow label="Market" value={review.terms.symbol} />
              <CardRow
                label="Account"
                value={environmentName(review.terms.environment)}
                numeric={false}
              />
              <CardRow label="Quantity" value={review.terms.quantity ?? '—'} />
              {type === 'update_protection' ? (
                <>
                  <CardRow
                    label="Stop loss"
                    value={
                      review.terms.stop_loss
                        ? formatUsd(Number(review.terms.stop_loss), { cents: true })
                        : 'Not set'
                    }
                  />
                  <CardRow
                    label="Take profit"
                    value={
                      review.terms.take_profit
                        ? formatUsd(Number(review.terms.take_profit), { cents: true })
                        : 'Not set'
                    }
                    last
                  />
                </>
              ) : (
                <CardRow
                  label="Execution"
                  value={
                    type === 'close_position'
                      ? 'Reduce-only market order'
                      : 'Unfilled quantity only'
                  }
                  numeric={false}
                  last
                />
              )}
            </Card>
            {type === 'close_position' ? (
              <Text tone="secondary" variant="footnote">
                Closes the reviewed quantity at market. Execution price and fees may differ from the
                current quote.
              </Text>
            ) : null}
            <Button
              title={`Confirm: ${titles[type].toLowerCase()}`}
              variant="destructive"
              loading={busy}
              onPress={() => void run(confirm)}
            />
          </>
        ) : (
          <>
            {type === 'update_protection' ? (
              <>
                <Field
                  label="New stop loss"
                  keyboardType="decimal-pad"
                  value={stop}
                  onChangeText={setStop}
                />
                <Field
                  label="New take profit"
                  keyboardType="decimal-pad"
                  value={target}
                  onChangeText={setTarget}
                />
                <Text tone="secondary" variant="footnote">
                  Leave a field empty to keep its current value.
                </Text>
              </>
            ) : null}
            {auth.factor ? (
              <>
                {auth.factor.secret ? (
                  <>
                    <Text variant="callout">
                      Add this key to your authenticator, then enter its code.
                    </Text>
                    <Text selectable>{auth.factor.secret}</Text>
                  </>
                ) : null}
                <Field
                  label="Authenticator code"
                  keyboardType="number-pad"
                  maxLength={6}
                  value={code}
                  onChangeText={(value) => setCode(value.replace(/\D/g, ''))}
                />
                <Button
                  title="Verify and review"
                  disabled={code.length !== 6}
                  loading={busy}
                  onPress={() => void run(verify)}
                />
              </>
            ) : (
              <Button
                title="Authenticate and review"
                variant="secondary"
                loading={busy}
                disabled={type === 'update_protection' && !stop.trim() && !target.trim()}
                onPress={() => void run(auth.start)}
              />
            )}
          </>
        )}
      </View>
    </Section>
  );
}
