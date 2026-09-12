import { useCallback, useRef, useState } from 'react';
import { Stack, router, useLocalSearchParams } from 'expo-router';
import { Keyboard, Linking, ScrollView, StyleSheet, View } from 'react-native';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { ApprovalScope } from '@/components/proposal/ApprovalScope';
import { ApprovalTray } from '@/components/proposal/ApprovalTray';
import { ExecutionActionPanel } from '@/components/proposal/ExecutionActionPanel';
import { CaseBlock } from '@/components/proposal/CaseBlock';
import { PriceLevels } from '@/components/proposal/PriceLevels';
import { ProposalHeadline } from '@/components/proposal/ProposalHeadline';
import {
  Button,
  Callout,
  Card,
  CardRow,
  EmptyState,
  ErrorState,
  Field,
  LoadingBlock,
  Section,
  Text,
  useToast,
} from '@/components/ui';
import {
  baseSymbol,
  entryPrice,
  evidenceState,
  expiryState,
  isAwaitingDecision,
  orderStatusPresentation,
  portfolioEffect,
} from '@/domain/proposal';
import * as haptics from '@/lib/haptics';
import { formatClock, formatRelativeIso, formatShare, formatUsd } from '@/lib/format';
import { useNow } from '@/lib/useNow';
import {
  usePortfolioSummary,
  useProposalOrder,
  useRejectTradeProposal,
  useTradeProposal,
} from '@/query/studioHooks';
import { useOrderApproval } from '@/query/useOrderApproval';
import { tokens } from '@/theme/tokens';

const CODE_LENGTH = 6;

export default function TradeProposalScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const now = useNow();
  const scroll = useRef<ScrollView>(null);
  const [code, setCode] = useState('');

  const proposalQuery = useTradeProposal(id);
  const portfolio = usePortfolioSummary();
  const reject = useRejectTradeProposal();
  const { showToast } = useToast();

  const proposal = proposalQuery.data ?? undefined;
  const approval = useOrderApproval(proposal);
  const showBrokerOrder =
    approval.submissionAttempted ||
    proposal?.status === 'submitted' ||
    proposal?.status === 'archived';
  const orderQuery = useProposalOrder(id, showBrokerOrder);
  const brokerOrder = orderQuery.data ?? approval.order;

  const close = useCallback(() => {
    if (router.canGoBack()) router.back();
    else router.replace('/signals');
  }, []);

  const startApproval = useCallback(async () => {
    if (!proposal) return;
    haptics.commit();
    await approval.start();
    // The code field renders at the end of the brief, so bring it into view
    // rather than leaving the user to hunt for the step that just appeared.
    requestAnimationFrame(() => scroll.current?.scrollToEnd({ animated: true }));
  }, [approval, proposal]);

  const confirmPlan = useCallback(async () => {
    Keyboard.dismiss();
    if (approval.review) await approval.submit();
    else await approval.verify(code);
    setCode('');
    requestAnimationFrame(() => scroll.current?.scrollToEnd({ animated: true }));
  }, [approval, code]);

  const pass = useCallback(() => {
    if (!proposal || approval.busy || approval.submissionAttempted) return;
    reject.mutate(proposal.id, {
      onSuccess: () => {
        haptics.selection();
        close();
      },
      onError: () => haptics.failure(),
    });
  }, [approval.busy, approval.submissionAttempted, close, proposal, reject]);

  const headerLeft = useCallback(
    () => <HeaderButton label="Close" onPress={close} symbol="xmark" />,
    [close],
  );

  if (!proposal) {
    return (
      <>
        <Stack.Screen options={{ headerLeft, title: 'Proposal' }} />
        <ScrollView
          contentContainerStyle={styles.content}
          contentInsetAdjustmentBehavior="automatic"
          style={styles.page}
        >
          {proposalQuery.isLoading ? (
            <LoadingBlock />
          ) : proposalQuery.isError ? (
            <ErrorState
              body="Could not load this proposal."
              onRetry={() => void proposalQuery.refetch()}
            />
          ) : (
            <EmptyState
              action={{ title: 'Back to signals', onPress: close }}
              body="Refresh your signals to check the latest proposal and order records."
              symbol="doc.questionmark"
              title="This proposal is no longer available"
            />
          )}
        </ScrollView>
      </>
    );
  }

  const awaiting = isAwaitingDecision(proposal) && !approval.submissionAttempted;
  const expiry = expiryState(proposal, now);
  const evidence = evidenceState(proposal);
  const effect = portfolioEffect(proposal, portfolio.data);
  const maxLoss = Number(proposal.estimated_max_loss);
  const notional = Number(proposal.quantity) * entryPrice(proposal);
  const costs =
    Number(proposal.estimated_fees) +
    Number(proposal.estimated_funding) +
    Number(proposal.estimated_slippage);
  const stepUpOpen = Boolean(approval.factor) && awaiting;
  const review = approval.review;
  const showTray = awaiting && !stepUpOpen && !review;
  const reviewExpired = Boolean(review && new Date(review.expires_at).getTime() <= now.getTime());
  const error = approval.error ?? reject.error?.message;
  const orderStatus = brokerOrder ? orderStatusPresentation(brokerOrder.state) : null;

  return (
    <>
      <Stack.Screen
        // The instrument is the screen's own headline; repeating it in the bar
        // would state the same fact twice within 40 points of each other.
        options={{ headerLeft, title: 'Trade proposal' }}
      />
      <ScrollView
        automaticallyAdjustKeyboardInsets
        contentContainerStyle={[styles.content, showTray && styles.contentWithTray]}
        contentInsetAdjustmentBehavior="automatic"
        keyboardShouldPersistTaps="handled"
        ref={scroll}
        style={styles.page}
      >
        <ProposalHeadline
          now={now}
          proposal={proposal}
          orderState={
            brokerOrder?.state ?? (approval.submissionAttempted ? 'submission_unknown' : undefined)
          }
        />

        <Section caption="Calculated by the strategy before entry." title="The plan">
          <PriceLevels proposal={proposal} />
        </Section>

        <Section caption="Sized against your live portfolio and mandate." title="Your position">
          <Card style={styles.rows}>
            <CardRow
              label="Position size"
              value={`${proposal.quantity} ${baseSymbol(proposal.symbol)}`}
            />
            <CardRow label="Notional value" value={formatUsd(notional, { cents: true })} />
            <CardRow
              detail={proposal.leverage === '1' ? 'No borrowed exposure' : undefined}
              label="Leverage"
              value={`${proposal.leverage}×`}
            />
            <CardRow
              detail={
                effect === null
                  ? 'Connect a portfolio to see the share of equity'
                  : 'Share of portfolio equity'
              }
              label="Estimated loss at stop"
              last
              tone="loss"
              value={`${formatUsd(maxLoss, { cents: true })}${effect === null ? '' : `   ${formatShare(effect)}`}`}
            />
          </Card>
        </Section>

        <Section caption={evidence.detail} title="The case">
          <CaseBlock body={proposal.thesis} title="What supports this trade" tone="support" />
          <CaseBlock
            body={proposal.opposing_case}
            title="The strongest case against it"
            tone="against"
          />
          <CaseBlock body={proposal.why_it_fits} title="Why it fits your portfolio" tone="fit" />
          <CaseBlock
            body={proposal.why_reject}
            title="Why you might reasonably pass"
            tone="reject"
          />
        </Section>

        <Section caption="Estimates. Actual costs are confirmed at execution." title="Costs">
          <Card style={styles.rows}>
            <CardRow
              label="Trading fees"
              value={formatUsd(Number(proposal.estimated_fees), { cents: true })}
            />
            <CardRow
              detail={
                proposal.category === 'linear'
                  ? 'Perpetual funding while held'
                  : 'Not applicable to spot'
              }
              label="Funding"
              value={formatUsd(Number(proposal.estimated_funding), { cents: true })}
            />
            <CardRow
              label="Slippage"
              value={formatUsd(Number(proposal.estimated_slippage), { cents: true })}
            />
            <CardRow label="Total estimated cost" last value={formatUsd(costs, { cents: true })} />
          </Card>
        </Section>

        <Section title="What you are approving">
          <ApprovalScope proposal={proposal} />
        </Section>

        {stepUpOpen ? (
          <Section
            title={approval.factor?.secret ? 'Set up your authenticator' : 'Verify your identity'}
          >
            {approval.factor?.secret ? (
              <View style={styles.setup}>
                <Text tone="secondary" variant="callout">
                  Add SignalOS to your authenticator, then enter its six-digit code.
                </Text>
                <Text selectable variant="body" style={styles.secret}>
                  {approval.factor.secret}
                </Text>
                <Button
                  variant="secondary"
                  title="Open authenticator"
                  onPress={() => {
                    if (approval.factor?.uri)
                      void Linking.openURL(approval.factor.uri).catch(() =>
                        showToast({
                          title: 'Add the key manually',
                          message: 'Copy the setup key above into your authenticator app.',
                          tone: 'info',
                        }),
                      );
                  }}
                />
              </View>
            ) : (
              <Text tone="secondary" variant="callout">
                Enter the current code from your authenticator. Verification does not submit an
                order.
              </Text>
            )}
            <View style={styles.rows}>
              <Field
                autoFocus
                keyboardType="number-pad"
                label="Authenticator code"
                maxLength={CODE_LENGTH}
                numeric
                onChangeText={(value) => setCode(value.replace(/\D/g, ''))}
                placeholder="000000"
                textContentType="oneTimeCode"
                value={code}
              />
            </View>
            <Button
              style={styles.rows}
              title="Verify and review"
              onPress={() => void confirmPlan()}
              loading={approval.busy}
              disabled={code.length !== CODE_LENGTH || reject.isPending}
            />
          </Section>
        ) : null}

        {review && awaiting ? (
          <Section
            title="Confirm this order"
            caption={`Review valid until ${formatClock(review.expires_at)}.`}
          >
            <Card style={styles.rows}>
              <CardRow
                label="Account"
                value={`${review.ticket.provider_id} · ${review.ticket.environment === 'mainnet' ? 'Live' : 'Testnet'}`}
              />
              <CardRow
                label="Market"
                value={`${review.ticket.symbol} · ${review.ticket.category === 'linear' ? 'Perpetual' : 'Spot'}`}
              />
              <CardRow
                label="Order"
                value={`${review.ticket.side === 'buy' ? 'Buy' : 'Sell'} · ${review.ticket.order_type}`}
              />
              <CardRow label="Quantity" value={review.ticket.quantity} />
              <CardRow label="Limit price" value={review.ticket.limit_price ?? 'Market'} />
              <CardRow
                label="Stop / target"
                value={`${review.ticket.stop_loss} / ${review.ticket.take_profit}`}
              />
              <CardRow label="Leverage" value={`${review.ticket.leverage}×`} />
              <CardRow
                label="Estimated loss at stop"
                value={`$${review.ticket.estimated_max_loss}`}
                last
              />
            </Card>
            <Text style={styles.rows} tone="secondary" variant="footnote">
              Stops do not guarantee the loss amount. Confirming sends only this reviewed order,
              subject to the backend checks.
            </Text>
            {reviewExpired ? (
              <Text tone="caution" style={styles.rows}>
                This review expired. Review the terms again before submitting.
              </Text>
            ) : null}
            <Button
              style={styles.rows}
              title={reviewExpired ? 'Review again' : 'Confirm and submit'}
              icon={reviewExpired ? 'arrow.clockwise' : 'paperplane'}
              loading={approval.busy}
              disabled={reject.isPending}
              onPress={() => void (reviewExpired ? startApproval() : confirmPlan())}
            />
          </Section>
        ) : null}

        {error && !(approval.submissionAttempted && brokerOrder) ? (
          <Callout
            body={error}
            live
            style={styles.notice}
            title={
              approval.submissionAttempted ? 'Check submission status' : 'Approval needs attention'
            }
            tone="caution"
          />
        ) : null}

        {showBrokerOrder ? (
          <Section title="Broker order">
            {brokerOrder && orderStatus ? (
              <>
                <Callout
                  title={orderStatus.label}
                  body={orderStatus.meaning}
                  live
                  tone={
                    orderStatus.tone === 'caution'
                      ? 'caution'
                      : orderStatus.tone === 'positive'
                        ? 'positive'
                        : 'info'
                  }
                />
                <Card style={styles.rows}>
                  <CardRow
                    label="Filled quantity"
                    value={brokerOrder.cumulative_executed_quantity}
                  />
                  <CardRow label="Remaining quantity" value={brokerOrder.leaves_quantity} />
                  <CardRow
                    label="Broker reference"
                    value={brokerOrder.broker_order_id ?? brokerOrder.broker_order_link_id}
                  />
                  <CardRow
                    label="Record updated"
                    value={formatRelativeIso(brokerOrder.updated_at, now.getTime())}
                    last
                  />
                </Card>
                {['acknowledged', 'partially_filled'].includes(brokerOrder.state) &&
                Number(brokerOrder.leaves_quantity) > 0 ? (
                  <ExecutionActionPanel type="cancel_order" targetId={brokerOrder.id} />
                ) : null}
              </>
            ) : (
              <Text tone="secondary" variant="callout">
                {orderQuery.isFetching
                  ? 'Checking the order record…'
                  : 'No order record is available yet. This does not confirm that nothing was submitted.'}
              </Text>
            )}
            {orderQuery.isError ? (
              <Text style={styles.rows} tone="caution">
                Could not refresh the order record. The last known state may be out of date.
              </Text>
            ) : null}
            <Button
              style={styles.rows}
              title="Refresh order status"
              icon="arrow.clockwise"
              variant="secondary"
              loading={orderQuery.isFetching}
              onPress={() => void orderQuery.refetch()}
            />
          </Section>
        ) : !awaiting ? (
          <Text style={styles.closed} tone="tertiary" variant="footnote">
            This proposal is closed. It stays here as a record of the decision and its reasoning.
          </Text>
        ) : null}
      </ScrollView>

      {showTray ? (
        <ApprovalTray
          expiry={expiry}
          maxLoss={maxLoss}
          onDismiss={close}
          onPass={pass}
          onPrimary={startApproval}
          passLoading={reject.isPending}
          primaryDisabled={reject.isPending}
          primaryLoading={approval.busy}
          primaryTitle="Review and approve"
        />
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.color.bg.canvas },
  content: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.sm,
    paddingBottom: tokens.space.xxl,
  },
  /** Clears the floating approval tray so nothing is trapped beneath it. */
  contentWithTray: { paddingBottom: 168 },
  rows: { marginTop: tokens.space.base },
  setup: { gap: tokens.space.md, marginTop: tokens.space.base },
  secret: {
    padding: tokens.space.base,
    backgroundColor: tokens.color.bg.surface,
    borderRadius: tokens.radius.md,
  },
  notice: { marginTop: tokens.space.xl },
  closed: { marginTop: tokens.space.xl },
});
