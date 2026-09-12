import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type {
  BrokerEnvironment,
  CreateBrokerConnectionInput,
  InvestmentProfileInput,
  ProposalFeedbackInput,
} from '@/domain/studio';
import { getStudioApi } from '@/services/api';
import { useAppStore } from '@/store/useAppStore';

export const studioKeys = {
  all: ['studio'] as const,
  onboarding: () => [...studioKeys.all, 'onboarding'] as const,
  profile: () => [...studioKeys.all, 'profile'] as const,
  providers: () => [...studioKeys.all, 'providers'] as const,
  connection: (id?: string) => [...studioKeys.all, 'connection', id] as const,
  portfolio: () => [...studioKeys.all, 'portfolio'] as const,
  positions: () => [...studioKeys.all, 'positions'] as const,
  market: (environment: BrokerEnvironment) => [...studioKeys.all, 'market', environment] as const,
  marketReview: (environment: BrokerEnvironment) =>
    [...studioKeys.all, 'market-review', environment] as const,
  marketAnalysisRequest: (id?: string) =>
    [...studioKeys.all, 'market-analysis-request', id] as const,
  proposals: () => [...studioKeys.all, 'proposals'] as const,
  memory: () => [...studioKeys.all, 'memory'] as const,
};

export function useStudioOnboardingState() {
  const owner = useAppStore((state) => state.ownerUserId);
  return useQuery({
    queryKey: [...studioKeys.onboarding(), owner],
    queryFn: () => getStudioApi().getOnboardingState(),
    enabled: Boolean(owner),
  });
}

/** Restore outside Supabase's auth callback, which holds its session lock. */
export function useRestoreAccount(userId: string | undefined, enabled: boolean) {
  const query = useQuery({
    queryKey: [...studioKeys.onboarding(), userId],
    queryFn: () => getStudioApi().getOnboardingState(),
    enabled: enabled && Boolean(userId),
  });
  useEffect(() => {
    if (enabled && userId && query.data) {
      useAppStore.getState().restoreAccount(userId, query.data);
    }
  }, [enabled, query.data, userId]);
  return query;
}

export function useInvestmentProfile() {
  const owner = useAppStore((state) => state.ownerUserId);
  return useQuery({
    queryKey: [...studioKeys.profile(), owner],
    queryFn: () => getStudioApi().getInvestmentProfile(),
    enabled: Boolean(owner),
  });
}

export function useSaveInvestmentProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: InvestmentProfileInput) => getStudioApi().saveInvestmentProfile(input),
    onSuccess: async (profile) => {
      useAppStore.getState().saveInvestmentProfile(profile);
      await Promise.all([
        client.invalidateQueries({ queryKey: studioKeys.profile() }),
        client.invalidateQueries({ queryKey: studioKeys.onboarding() }),
        client.invalidateQueries({ queryKey: studioKeys.portfolio() }),
      ]);
    },
  });
}

export function useBrokerProviders() {
  return useQuery({
    queryKey: studioKeys.providers(),
    queryFn: () => getStudioApi().listBrokerProviders(),
    staleTime: 5 * 60_000,
  });
}

export function useCreateBrokerConnection() {
  const client = useQueryClient();
  return useMutation({
    onMutate: () => ({ owner: useAppStore.getState().ownerUserId }),
    mutationFn: (input: CreateBrokerConnectionInput) =>
      getStudioApi().createBrokerConnection(input),
    onSuccess: (connection, _input, context) => {
      if (useAppStore.getState().ownerUserId !== context?.owner) return;
      useAppStore.getState().saveBrokerConnection(connection, context.owner);
      client.setQueryData(studioKeys.connection(connection.id), connection);
    },
  });
}

export function useDisconnectBroker() {
  const client = useQueryClient();
  return useMutation({
    onMutate: () => ({ owner: useAppStore.getState().ownerUserId }),
    mutationFn: (connectionId: string) => getStudioApi().deleteBrokerConnection(connectionId),
    onSuccess: async (_data, connectionId, context) => {
      const state = useAppStore.getState();
      if (state.ownerUserId !== context?.owner || state.brokerConnection?.id !== connectionId)
        return;
      // Local portfolio history belongs to the disconnected account and must go
      // with it, rather than becoming a baseline for a different one.
      useAppStore.getState().clearBrokerConnection();
      await client.invalidateQueries({ queryKey: studioKeys.all });
    },
  });
}

export function useVerifyBrokerConnection() {
  const client = useQueryClient();
  return useMutation({
    onMutate: () => ({ owner: useAppStore.getState().ownerUserId }),
    mutationFn: (connectionId: string) => getStudioApi().verifyBrokerConnection(connectionId),
    onSuccess: (connection, _id, context) => {
      if (useAppStore.getState().ownerUserId !== context?.owner) return;
      useAppStore.getState().saveBrokerConnection(connection, context.owner);
      client.setQueryData(studioKeys.connection(connection.id), connection);
    },
  });
}

export function useSyncBrokerConnection() {
  const client = useQueryClient();
  return useMutation({
    onMutate: () => ({ owner: useAppStore.getState().ownerUserId }),
    mutationFn: (connectionId: string) => getStudioApi().syncBrokerConnection(connectionId),
    onSuccess: async (connection, _id, context) => {
      const state = useAppStore.getState();
      if (state.ownerUserId !== context?.owner || state.brokerConnection?.id !== connection.id)
        return;
      useAppStore.getState().saveBrokerConnection(connection, context.owner);
      client.setQueryData(studioKeys.connection(connection.id), connection);
      await Promise.all([
        client.invalidateQueries({ queryKey: studioKeys.onboarding() }),
        client.invalidateQueries({ queryKey: studioKeys.portfolio() }),
        client.invalidateQueries({ queryKey: studioKeys.positions() }),
        client.invalidateQueries({ queryKey: studioKeys.proposals() }),
      ]);
    },
  });
}

export function useSwitchBrokerContext() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      connectionId,
      environment,
    }: {
      connectionId: string;
      environment: BrokerEnvironment;
    }) => getStudioApi().switchBrokerContext(connectionId, environment),
    onSuccess: async (context) => {
      await client.cancelQueries({ queryKey: studioKeys.all });
      const connection = await getStudioApi().getBrokerConnection(context.connection_id);
      useAppStore.getState().saveBrokerConnection(connection, context.user_id);
      await client.invalidateQueries({ queryKey: studioKeys.all });
    },
  });
}

export function useLatestMarketScan(environment: BrokerEnvironment) {
  return useQuery({
    queryKey: studioKeys.market(environment),
    queryFn: () => getStudioApi().getLatestMarketScan(environment),
  });
}

export function useRunMarketScan(environment: BrokerEnvironment) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => getStudioApi().runMarketScan(environment),
    onSuccess: (scan) => client.setQueryData(studioKeys.market(environment), scan),
  });
}

export function useLatestMarketReview(environment: BrokerEnvironment) {
  const owner = useAppStore((state) => state.ownerUserId);
  const connectionId = useAppStore((state) => state.brokerConnection?.id);
  return useQuery({
    queryKey: [...studioKeys.marketReview(environment), owner, connectionId],
    enabled: Boolean(owner),
    queryFn: () => getStudioApi().getLatestMarketReview(environment),
    refetchInterval: 60_000,
  });
}

export function useRequestMarketAnalysis(environment: BrokerEnvironment) {
  return useMutation({
    mutationFn: () => getStudioApi().requestMarketAnalysis(environment),
  });
}

export function useMarketAnalysisRequest(requestId: string | null) {
  return useQuery({
    queryKey: studioKeys.marketAnalysisRequest(requestId ?? undefined),
    queryFn: () => getStudioApi().getMarketAnalysisRequest(requestId!),
    enabled: Boolean(requestId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 2_000 : false;
    },
  });
}

export function usePortfolioSummary() {
  const owner = useAppStore((state) => state.ownerUserId);
  const connectionId = useAppStore((state) => state.brokerConnection?.id);
  return useQuery({
    queryKey: [...studioKeys.portfolio(), owner, connectionId],
    enabled: Boolean(owner && connectionId),
    queryFn: async () => {
      const summary = await getStudioApi().getPortfolioSummary();
      if (summary && summary.connection_id !== connectionId) return null;
      // Retain the capture so "change over 24h" has a baseline to measure
      // against; the backend only ever serves the current snapshot.
      if (summary && useAppStore.getState().ownerUserId === owner) {
        useAppStore.getState().recordPortfolio(summary);
      }
      return summary;
    },
  });
}

export function useOpenPositions() {
  const owner = useAppStore((state) => state.ownerUserId);
  const connectionId = useAppStore((state) => state.brokerConnection?.id);
  return useQuery({
    queryKey: [...studioKeys.positions(), owner, connectionId],
    queryFn: () => getStudioApi().listOpenPositions(connectionId),
    enabled: Boolean(owner && connectionId),
  });
}

export function useTradeProposals() {
  const owner = useAppStore((state) => state.ownerUserId);
  const connectionId = useAppStore((state) => state.brokerConnection?.id);
  return useQuery({
    queryKey: [...studioKeys.proposals(), owner, connectionId],
    enabled: Boolean(owner && connectionId),
    queryFn: async () => {
      const proposals = await getStudioApi().listTradeProposals(connectionId);
      const state = useAppStore.getState();
      if (state.ownerUserId === owner && state.brokerConnection?.id === connectionId) {
        state.saveTradeProposals(proposals);
      }
      return proposals;
    },
    refetchInterval: 60_000,
  });
}

export function useTradeProposal(proposalId: string) {
  const owner = useAppStore((state) => state.ownerUserId);
  return useQuery({
    queryKey: [...studioKeys.proposals(), owner, 'detail', proposalId],
    queryFn: () => getStudioApi().getTradeProposal(proposalId),
    enabled: Boolean(owner && proposalId),
  });
}

export function useRejectTradeProposal() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (proposalId: string) => getStudioApi().rejectTradeProposal(proposalId),
    onSuccess: () => client.invalidateQueries({ queryKey: studioKeys.proposals() }),
  });
}

export function useProposalFeedback() {
  return useMutation({
    mutationFn: ({ proposalId, input }: { proposalId: string; input: ProposalFeedbackInput }) =>
      getStudioApi().addTradeProposalFeedback(proposalId, input),
  });
}

export function useProposalOrder(proposalId: string, enabled: boolean) {
  const owner = useAppStore((state) => state.ownerUserId);
  return useQuery({
    queryKey: [...studioKeys.proposals(), owner, proposalId, 'order'],
    enabled: Boolean(owner && enabled),
    queryFn: async () => {
      const orders = await getStudioApi().listBrokerOrders(proposalId);
      return orders.find((order) => order.proposal_id === proposalId) ?? null;
    },
  });
}

export function useMemory() {
  const owner = useAppStore((state) => state.ownerUserId);
  return useQuery({
    queryKey: [...studioKeys.memory(), owner],
    enabled: Boolean(owner),
    queryFn: async () => {
      const memories = await getStudioApi().listMemory();
      if (useAppStore.getState().ownerUserId === owner) {
        useAppStore.getState().saveMemories(memories);
      }
      return memories;
    },
  });
}

export function useDeleteMemory() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (memoryId: string) => getStudioApi().deleteMemory(memoryId),
    onSuccess: () => client.invalidateQueries({ queryKey: studioKeys.memory() }),
  });
}

export function useResetLearnedPreferences() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => getStudioApi().resetLearnedPreferences(),
    onSuccess: () => client.invalidateQueries({ queryKey: studioKeys.memory() }),
  });
}
