import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { type EquitySnapshot, recordEquity, snapshotFrom } from '@/domain/portfolio';
import { type ProfileDraft, draftFromProfile, emptyProfileDraft } from '@/domain/profile';
import type {
  BrokerConnection,
  BrokerEnvironment,
  InvestmentProfile,
  OnboardingState,
  PortfolioSummary,
  TradeProposal,
  UserMemory,
} from '@/domain/studio';

export interface Account {
  firstName: string;
  lastName: string;
  email: string;
}

const emptyAccount: Account = { firstName: '', lastName: '', email: '' };

interface AppState {
  hydrated: boolean;
  ownerUserId: string | null;
  restoredUserId: string | null;
  /** True only once the profile, disclosures, and a healthy connection exist. */
  hasOnboarded: boolean;
  account: Account;
  profileDraft: ProfileDraft;
  investmentProfile: InvestmentProfile | null;
  brokerConnection: BrokerConnection | null;
  brokerEnvironment: BrokerEnvironment;
  tradeProposals: TradeProposal[];
  memories: UserMemory[];
  /** Locally retained equity captures; the backend serves only the latest. */
  equityHistory: EquitySnapshot[];

  setHydrated(value: boolean): void;
  setAccount(value: Account): void;
  bindAuthenticatedUser(userId: string, account: Account): void;
  restoreAccount(userId: string, state: OnboardingState): void;
  setProfileDraft(value: Partial<ProfileDraft>): void;
  saveInvestmentProfile(value: InvestmentProfile): void;
  saveBrokerConnection(value: BrokerConnection, userId: string | null): void;
  clearBrokerConnection(): void;
  setBrokerEnvironment(value: BrokerEnvironment): void;
  saveTradeProposals(value: TradeProposal[]): void;
  saveMemories(value: UserMemory[]): void;
  recordPortfolio(summary: PortfolioSummary): void;
  completeOnboarding(): void;
  deleteLocalAccount(): void;
}

const reset = {
  ownerUserId: null,
  restoredUserId: null,
  hasOnboarded: false,
  account: emptyAccount,
  profileDraft: emptyProfileDraft,
  investmentProfile: null,
  brokerConnection: null,
  brokerEnvironment: 'mainnet' as BrokerEnvironment,
  tradeProposals: [],
  memories: [],
  equityHistory: [],
};

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      hydrated: false,
      ...reset,

      setHydrated: (hydrated) => set({ hydrated }),
      setAccount: (account) => set({ account }),
      bindAuthenticatedUser: (userId, account) => {
        const current = get();
        if (current.ownerUserId !== userId) {
          set({ ...reset, ownerUserId: userId, account });
          return;
        }
        set({ ownerUserId: userId, account });
      },
      restoreAccount: (userId, state) => {
        if (get().ownerUserId !== userId) return;
        const connectionChanged = get().brokerConnection?.id !== state.broker_connection?.id;
        set({
          restoredUserId: userId,
          hasOnboarded: state.studio_unlocked,
          investmentProfile: state.investment_profile,
          profileDraft: state.investment_profile
            ? draftFromProfile(state.investment_profile)
            : emptyProfileDraft,
          brokerConnection: state.broker_connection,
          brokerEnvironment: state.broker_connection?.environment ?? 'mainnet',
          ...(connectionChanged ? { equityHistory: [], tradeProposals: [] } : {}),
        });
      },

      setProfileDraft: (value) => set({ profileDraft: { ...get().profileDraft, ...value } }),
      saveInvestmentProfile: (investmentProfile) => {
        if (get().ownerUserId !== investmentProfile.user_id) return;
        set({ investmentProfile, profileDraft: draftFromProfile(investmentProfile) });
      },

      saveBrokerConnection: (brokerConnection, userId) => {
        if (!userId || get().ownerUserId !== userId) return;
        set({
          brokerConnection,
          brokerEnvironment: brokerConnection.environment,
          ...(get().brokerConnection?.id !== brokerConnection.id
            ? { equityHistory: [], tradeProposals: [] }
            : {}),
        });
      },
      clearBrokerConnection: () =>
        set({ brokerConnection: null, tradeProposals: [], equityHistory: [], hasOnboarded: false }),
      // Environments are isolated, so proposals and equity history from the old
      // context must not survive the switch.
      setBrokerEnvironment: (brokerEnvironment) =>
        set({ brokerEnvironment, tradeProposals: [], equityHistory: [] }),

      saveTradeProposals: (tradeProposals) => set({ tradeProposals }),
      saveMemories: (memories) => set({ memories }),
      recordPortfolio: (summary) => {
        if (get().brokerConnection?.id !== summary.connection_id) return;
        set({ equityHistory: recordEquity(get().equityHistory, snapshotFrom(summary)) });
      },

      completeOnboarding: () => {
        const { brokerConnection, investmentProfile } = get();
        if (brokerConnection?.status === 'healthy' && investmentProfile?.disclosures_accepted) {
          set({ hasOnboarded: true });
        }
      },
      deleteLocalAccount: () => set(reset),
    }),
    {
      // Authentication lives in Supabase SecureStore, never in this UI cache.
      name: 'signalos-app-state-v9',
      storage: createJSONStorage(() => AsyncStorage),
      partialize: ({
        ownerUserId,
        hasOnboarded,
        account,
        profileDraft,
        investmentProfile,
        brokerConnection,
        brokerEnvironment,
        tradeProposals,
        memories,
        equityHistory,
      }) => ({
        ownerUserId,
        hasOnboarded,
        account,
        profileDraft,
        investmentProfile,
        brokerConnection,
        brokerEnvironment,
        tradeProposals,
        memories,
        equityHistory,
      }),
      onRehydrateStorage: () => (state) => state?.setHydrated(true),
    },
  ),
);
