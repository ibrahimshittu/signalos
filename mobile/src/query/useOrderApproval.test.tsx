import { beforeEach, expect, it, jest } from '@jest/globals';
import { act, renderHook } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { PropsWithChildren } from 'react';
import type { TradeProposal } from '@/domain/studio';
import { getStudioApi } from '@/services/api';
import { SignalOSApiError } from '@/services/api/transport';
import { supabase } from '@/services/auth/supabase';
import { useOrderApproval } from './useOrderApproval';

jest.mock('@/services/api', () => ({ getStudioApi: jest.fn() }));
jest.mock('@/services/auth/supabase', () => ({
  supabase: {
    auth: {
      mfa: {
        listFactors: jest.fn(),
        enroll: jest.fn(),
        challengeAndVerify: jest.fn(),
        unenroll: jest.fn(),
      },
    },
  },
}));

const proposal = {
  id: 'proposal-1',
  proposal_hash: 'a'.repeat(64),
  status: 'available',
} as TradeProposal;
const review = {
  id: 'review-1',
  ticket: { proposal_id: proposal.id, proposal_hash: proposal.proposal_hash },
  expires_at: new Date(Date.now() + 120_000).toISOString(),
};
const order = { id: 'order-1', proposal_id: proposal.id, state: 'submission_unknown' };

async function setup() {
  const api = {
    createOrderReview: jest.fn<() => Promise<typeof review>>().mockResolvedValue(review),
    submitTradeOrder: jest.fn<() => Promise<typeof order>>().mockResolvedValue(order),
  };
  (getStudioApi as jest.Mock).mockReturnValue(api);
  (supabase.auth.mfa.listFactors as jest.Mock<() => Promise<unknown>>).mockResolvedValue({
    data: { totp: [{ id: 'factor-1', status: 'verified' }] },
    error: null,
  });
  (supabase.auth.mfa.challengeAndVerify as jest.Mock<() => Promise<unknown>>).mockResolvedValue({
    data: {},
    error: null,
  });
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { ...(await renderHook(() => useOrderApproval(proposal), { wrapper })), api };
}

beforeEach(() => {
  jest.clearAllMocks();
});

it('verifies MFA, waits for explicit review confirmation, and preserves an uncertain broker outcome', async () => {
  const { result, api } = await setup();
  await act(async () => {
    await result.current.start();
  });
  await act(async () => {
    await result.current.verify('123456');
  });
  expect(supabase.auth.mfa.challengeAndVerify).toHaveBeenCalledWith({
    factorId: 'factor-1',
    code: '123456',
  });
  expect(api.createOrderReview).toHaveBeenCalledWith(proposal.id);
  expect(api.submitTradeOrder).not.toHaveBeenCalled();
  expect(result.current.review).toEqual(review);

  await act(async () => {
    await Promise.all([result.current.submit(), result.current.submit()]);
  });
  expect(api.submitTradeOrder).toHaveBeenCalledTimes(1);
  expect(api.submitTradeOrder).toHaveBeenCalledWith(proposal.id, {
    review_id: review.id,
    proposal_hash: proposal.proposal_hash,
    idempotency_key: `signalos:${proposal.id}`,
  });
  expect(result.current.order?.state).toBe('submission_unknown');
  expect(result.current.submissionAttempted).toBe(true);
});

it('does not create a review or submit when Supabase rejects the authenticator code', async () => {
  const { result, api } = await setup();
  (supabase.auth.mfa.challengeAndVerify as jest.Mock<() => Promise<unknown>>).mockResolvedValue({
    data: null,
    error: { code: 'mfa_verification_failed' },
  });
  await act(async () => {
    await result.current.start();
  });
  await act(async () => {
    await result.current.verify('000000');
  });
  await act(async () => {
    await result.current.submit();
  });
  expect(result.current.error).toContain('code');
  expect(result.current.review).toBeNull();
  expect(api.createOrderReview).not.toHaveBeenCalled();
  expect(api.submitTradeOrder).not.toHaveBeenCalled();
});

it('allows a new review after a definite preflight rejection without claiming an unknown order', async () => {
  const { result, api } = await setup();
  api.submitTradeOrder.mockRejectedValue(
    new SignalOSApiError('Current mandate changed.', 409, false),
  );
  await act(async () => {
    await result.current.start();
  });
  await act(async () => {
    await result.current.verify('123456');
  });
  await act(async () => {
    await result.current.submit();
  });
  expect(result.current.submissionAttempted).toBe(false);
  expect(result.current.review).toBeNull();
  expect(result.current.error).toBe('Current mandate changed.');
});
