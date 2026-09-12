import { expect, it, jest } from '@jest/globals';
import { act, fireEvent, render } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { getStudioApi } from '@/services/api';
import { useAuthenticator } from '@/services/auth/useAuthenticator';
import { ExecutionActionPanel } from './ExecutionActionPanel';

jest.mock('@/services/api', () => ({ getStudioApi: jest.fn() }));
jest.mock('@/services/auth/useAuthenticator', () => ({ useAuthenticator: jest.fn() }));

it('requires a separate confirmation of fresh close terms after authentication', async () => {
  const review = {
    id: 'review-1',
    action_hash: 'a'.repeat(64),
    expires_at: new Date(Date.now() + 120_000).toISOString(),
    terms: {
      target_id: 'position-1',
      action_type: 'close_position',
      environment: 'testnet',
      symbol: 'BTCUSDT',
      quantity: '0.01',
    },
  };
  const api = {
    createExecutionReview: jest.fn<() => Promise<typeof review>>().mockResolvedValue(review),
    confirmExecutionAction: jest
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ id: 'action-1', state: 'acknowledged' }),
    getExecutionAction: jest
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ id: 'action-1', state: 'completed' }),
  };
  (getStudioApi as jest.Mock).mockReturnValue(api);
  (useAuthenticator as jest.Mock).mockReturnValue({
    factor: { id: 'factor-1' },
    start: jest.fn(),
    verify: jest.fn<() => Promise<boolean>>().mockResolvedValue(true),
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const view = await render(
    <QueryClientProvider client={client}>
      <ExecutionActionPanel type="close_position" targetId="position-1" />
    </QueryClientProvider>,
  );
  await fireEvent.changeText(view.getByLabelText('Authenticator code'), '123456');
  await act(async () => {
    await fireEvent.press(view.getByText('Verify and review'));
  });
  expect(api.createExecutionReview).toHaveBeenCalledWith('close_position', 'position-1', {});
  expect(api.confirmExecutionAction).not.toHaveBeenCalled();
  expect(view.getByText('0.01')).toBeOnTheScreen();
  await act(async () => {
    await fireEvent.press(view.getByText('Confirm: close position'));
  });
  expect(api.confirmExecutionAction).toHaveBeenCalledTimes(1);
  expect(api.confirmExecutionAction).toHaveBeenCalledWith('close_position', 'position-1', {
    review_id: 'review-1',
    action_hash: review.action_hash,
    idempotency_key: `signalos-action:${review.action_hash}`,
  });
  await view.unmount();
  client.clear();
});
