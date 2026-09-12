import { beforeEach, expect, it, jest } from '@jest/globals';
import * as SecureStore from 'expo-secure-store';
import * as Notifications from 'expo-notifications';
import { getStudioApi } from '@/services/api';
import { disablePush, proposalFromNotification, registerPush } from './push';

jest.mock('expo-constants', () => ({
  __esModule: true,
  default: {
    expoConfig: { extra: { eas: { projectId: '11111111-1111-4111-8111-111111111111' } } },
  },
}));
jest.mock('expo-crypto', () => ({ randomUUID: () => '22222222-2222-4222-8222-222222222222' }));
jest.mock('expo-notifications', () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
}));
jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));
jest.mock('@/services/api', () => ({ getStudioApi: jest.fn() }));
jest.mock('@/store/useAppStore', () => ({
  useAppStore: { getState: () => ({ ownerUserId: 'user-a' }) },
}));

let stored: string | null;
const register = jest.fn<() => Promise<void>>();
const remove = jest.fn<() => Promise<void>>();

beforeEach(() => {
  jest.clearAllMocks();
  stored = null;
  (SecureStore.getItemAsync as jest.Mock<() => Promise<string | null>>).mockImplementation(
    async () => stored,
  );
  (
    SecureStore.setItemAsync as jest.Mock<(key: string, value: string) => Promise<void>>
  ).mockImplementation(async (_key, value) => {
    stored = value;
  });
  (SecureStore.deleteItemAsync as jest.Mock<() => Promise<void>>).mockImplementation(async () => {
    stored = null;
  });
  (Notifications.getPermissionsAsync as jest.Mock<() => Promise<unknown>>).mockResolvedValue({
    granted: false,
  });
  (Notifications.requestPermissionsAsync as jest.Mock<() => Promise<unknown>>).mockResolvedValue({
    granted: true,
  });
  (Notifications.getExpoPushTokenAsync as jest.Mock<() => Promise<unknown>>).mockResolvedValue({
    data: 'ExpoPushToken[test-token-only]',
  });
  register.mockResolvedValue();
  remove.mockResolvedValue();
  (getStudioApi as jest.Mock).mockReturnValue({
    registerNotificationDevice: register,
    removeNotificationDevice: remove,
  });
});

it('only registers after opt-in and revokes the exact installation on sign-out', async () => {
  await registerPush('user-a');
  expect(Notifications.requestPermissionsAsync).not.toHaveBeenCalled();
  expect(register).not.toHaveBeenCalled();
  await registerPush('user-a', true);
  expect(register).toHaveBeenCalledWith(
    '22222222-2222-4222-8222-222222222222',
    expect.objectContaining({ expo_push_token: 'ExpoPushToken[test-token-only]' }),
  );
  await disablePush('user-a');
  expect(remove).toHaveBeenCalledWith('22222222-2222-4222-8222-222222222222');
  expect(stored).toBeNull();
});

it('cannot register another account’s saved installation or follow an arbitrary notification URL', async () => {
  stored = JSON.stringify({
    userId: 'user-b',
    installationId: '22222222-2222-4222-8222-222222222222',
  });
  await expect(registerPush('user-a', true)).rejects.toThrow('previous account');
  expect(register).not.toHaveBeenCalled();
  expect(
    proposalFromNotification({ type: 'proposal_available', proposal_id: 'https://example.com' }),
  ).toBeNull();
  expect(
    proposalFromNotification({
      type: 'proposal_available',
      proposal_id: '33333333-3333-4333-8333-333333333333',
    }),
  ).toBe('33333333-3333-4333-8333-333333333333');
});
