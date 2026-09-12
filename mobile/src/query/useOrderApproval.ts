import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { BrokerOrder, OrderReview, TradeProposal } from '@/domain/studio';
import { getStudioApi } from '@/services/api';
import { SignalOSApiError } from '@/services/api/transport';
import { useAuthenticator } from '@/services/auth/useAuthenticator';
import { studioKeys } from './studioHooks';

/** MFA proves identity; only a separate tap submits the immutable order review. */
export function useOrderApproval(proposal: TradeProposal | undefined) {
  const client = useQueryClient();
  const authenticator = useAuthenticator();
  const [review, setReview] = useState<OrderReview | null>(null);
  const [order, setOrder] = useState<BrokerOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submissionAttempted, setSubmissionAttempted] = useState(false);
  const locked = useRef(false);
  const attempted = useRef(false);

  function begin() {
    if (locked.current || attempted.current || proposal?.status !== 'available') return false;
    locked.current = true;
    setBusy(true);
    setError(null);
    return true;
  }

  function finish() {
    locked.current = false;
    setBusy(false);
  }

  async function start() {
    if (!begin()) return;
    setReview(null);
    try {
      await authenticator.start();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not open authentication. Try again.',
      );
    } finally {
      finish();
    }
  }

  async function verify(code: string) {
    if (!authenticator.factor || !proposal || !/^\d{6}$/.test(code) || !begin()) return;
    try {
      if (!(await authenticator.verify(code))) return;
      const ticket = await getStudioApi().createOrderReview(proposal.id);
      if (
        ticket.ticket.proposal_id !== proposal.id ||
        ticket.ticket.proposal_hash !== proposal.proposal_hash
      ) {
        throw new Error(
          'The proposal changed. Close it and open the latest version before approving.',
        );
      }
      setReview(ticket);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Could not verify the order review. Try again.',
      );
    } finally {
      finish();
    }
  }

  async function submit() {
    if (!proposal || !review || !begin()) return;
    if (new Date(review.expires_at).getTime() <= Date.now()) {
      setReview(null);
      setError('This order review expired. Review the latest terms again.');
      finish();
      return;
    }
    attempted.current = true;
    setSubmissionAttempted(true);
    try {
      setOrder(
        await getStudioApi().submitTradeOrder(proposal.id, {
          review_id: review.id,
          proposal_hash: review.ticket.proposal_hash,
          // Stable even after a timeout or screen reopen. Never create a second attempt key.
          idempotency_key: `signalos:${proposal.id}`,
        }),
      );
    } catch (cause) {
      // These responses are issued before an order is submitted. Transport and
      // server failures remain uncertain and must be reconciled, not retried blindly.
      if (cause instanceof SignalOSApiError && [401, 403, 404, 409, 422].includes(cause.status)) {
        attempted.current = false;
        setSubmissionAttempted(false);
        setReview(null);
        setError(cause.message);
      } else {
        setError('Submission could not be confirmed. Check the order status before trying again.');
      }
    } finally {
      finish();
      void client.invalidateQueries({ queryKey: studioKeys.proposals() });
    }
  }

  return {
    factor: authenticator.factor,
    review,
    order,
    error,
    busy,
    submissionAttempted,
    start,
    verify,
    submit,
  };
}
