import { beforeEach, expect, it, jest } from '@jest/globals';
import type { BrokerConnection, InvestmentProfile, OnboardingState } from '@/domain/studio';
import { useAppStore } from './useAppStore';

jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(async () => null),
  setItem: jest.fn(async () => {}),
  removeItem: jest.fn(async () => {}),
}));

const account = { firstName: 'Test', lastName: 'Investor', email: 'test@example.com' };
const connection = {
  id: 'connection-a',
  provider_id: 'bybit',
  environment: 'testnet',
  status: 'healthy',
} as BrokerConnection;
const restored = {
  studio_unlocked: true,
  investment_profile: null,
  broker_connection: connection,
} as OnboardingState;

beforeEach(() => useAppStore.getState().deleteLocalAccount());

it('restores the server account and clears it when another identity signs in', () => {
  useAppStore.getState().bindAuthenticatedUser('user-a', account);
  useAppStore.getState().restoreAccount('user-a', restored);
  expect(useAppStore.getState()).toMatchObject({
    restoredUserId: 'user-a',
    brokerEnvironment: 'testnet',
    hasOnboarded: true,
    brokerConnection: connection,
  });
  useAppStore.getState().bindAuthenticatedUser('user-b', account);
  expect(useAppStore.getState()).toMatchObject({
    ownerUserId: 'user-b',
    restoredUserId: null,
    hasOnboarded: false,
    brokerConnection: null,
    tradeProposals: [],
    equityHistory: [],
  });
});

it('ignores late profile, connection, and restoration responses from the signed-out user', () => {
  useAppStore.getState().bindAuthenticatedUser('user-b', account);
  useAppStore.getState().restoreAccount('user-a', restored);
  useAppStore.getState().saveBrokerConnection(connection, 'user-a');
  useAppStore.getState().saveInvestmentProfile({ user_id: 'user-a' } as InvestmentProfile);
  expect(useAppStore.getState()).toMatchObject({
    restoredUserId: null,
    brokerConnection: null,
    investmentProfile: null,
  });
});
