import {
  SubmitOrderInput,
  BrokerEnvironment,
  CreateBrokerConnectionInput,
  InvestmentProfileInput,
  InvestmentStudioApi,
  ProposalFeedbackInput,
  ExecutionActionType,
  ConfirmExecutionActionInput,
  UpdateProtectionInput,
  PersonalizedPreferencesUpdate,
} from '@/domain/studio';
import { SignalOSApiError, SignalOSHttpClient, SignalOSHttpOptions } from './transport';

function executionPath(type: ExecutionActionType, id: string) {
  const target = encodeURIComponent(id);
  if (type === 'cancel_order') return `/v1/orders/${target}/cancel`;
  return `/v1/positions/${target}/${type === 'close_position' ? 'close' : 'protection'}`;
}

export class HttpSignalOSApi implements InvestmentStudioApi {
  private readonly client: SignalOSHttpClient;

  constructor(options: SignalOSHttpOptions = {}) {
    this.client = new SignalOSHttpClient(options);
  }

  async registerNotificationDevice(
    installationId: string,
    input: { platform: 'ios' | 'android'; expo_push_token: string; expo_project_id: string },
  ) {
    await this.client.request(`/v1/me/notification-devices/${encodeURIComponent(installationId)}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    });
  }

  async removeNotificationDevice(installationId: string) {
    try {
      await this.client.request(
        `/v1/me/notification-devices/${encodeURIComponent(installationId)}`,
        { method: 'DELETE' },
      );
    } catch (error) {
      if (!(error instanceof SignalOSApiError && error.status === 404)) throw error;
    }
  }

  getOnboardingState() {
    return this.client.request<import('@/domain/studio').OnboardingState>(
      '/v1/me/onboarding-state',
    );
  }

  async getInvestmentProfile() {
    try {
      return await this.client.request<import('@/domain/studio').InvestmentProfile>(
        '/v1/me/investment-profile',
      );
    } catch (error) {
      if (error instanceof SignalOSApiError && error.status === 404) return null;
      throw error;
    }
  }

  saveInvestmentProfile(input: InvestmentProfileInput) {
    return this.client.request<import('@/domain/studio').InvestmentProfile>(
      '/v1/me/investment-profile',
      {
        method: 'PUT',
        body: JSON.stringify(input),
      },
    );
  }

  listBrokerProviders() {
    return this.client.request<import('@/domain/studio').BrokerProvider[]>('/v1/broker-providers');
  }

  async getPersonalization() {
    try {
      return await this.client.request<import('@/domain/studio').PersonalizedPolicy>(
        '/v1/me/personalization',
      );
    } catch (error) {
      if (error instanceof SignalOSApiError && error.status === 404) return null;
      throw error;
    }
  }

  updatePersonalization(input: PersonalizedPreferencesUpdate) {
    return this.client.request<import('@/domain/studio').PersonalizedPolicy>(
      '/v1/me/personalization',
      { method: 'PUT', body: JSON.stringify(input) },
    );
  }

  generatePersonalization() {
    return this.client.request<import('@/domain/studio').PersonalizedPolicy>(
      '/v1/me/personalization/generate',
      { method: 'POST' },
    );
  }

  createBrokerConnection(input: CreateBrokerConnectionInput) {
    return this.client.request<import('@/domain/studio').BrokerConnection>(
      '/v1/broker-connections',
      {
        method: 'POST',
        body: JSON.stringify(input),
      },
    );
  }

  getBrokerConnection(connectionId: string) {
    return this.client.request<import('@/domain/studio').BrokerConnection>(
      `/v1/broker-connections/${encodeURIComponent(connectionId)}`,
    );
  }

  deleteBrokerConnection(connectionId: string) {
    return this.client.request<void>(`/v1/broker-connections/${encodeURIComponent(connectionId)}`, {
      method: 'DELETE',
    });
  }

  verifyBrokerConnection(connectionId: string) {
    return this.client.request<import('@/domain/studio').BrokerConnection>(
      `/v1/broker-connections/${encodeURIComponent(connectionId)}/verify`,
      { method: 'POST' },
    );
  }

  syncBrokerConnection(connectionId: string) {
    return this.client.request<import('@/domain/studio').BrokerConnection>(
      `/v1/broker-connections/${encodeURIComponent(connectionId)}/sync`,
      { method: 'POST' },
    );
  }

  switchBrokerContext(connectionId: string, environment: BrokerEnvironment) {
    return this.client.request<import('@/domain/studio').BrokerContext>(
      '/v1/broker-context/switch',
      {
        method: 'POST',
        body: JSON.stringify({ connection_id: connectionId, environment }),
      },
    );
  }

  async getPortfolioSummary() {
    try {
      return await this.client.request<import('@/domain/studio').PortfolioSummary>(
        '/v1/portfolio-summary',
      );
    } catch (error) {
      if (error instanceof SignalOSApiError && error.status === 404) return null;
      throw error;
    }
  }

  listOpenPositions(connectionId?: string) {
    return this.client.request<import('@/domain/studio').BrokerPosition[]>(
      `/v1/positions?open_only=true${connectionId ? `&connection_id=${encodeURIComponent(connectionId)}` : ''}`,
    );
  }

  getPosition(positionId: string) {
    return this.client.request<import('@/domain/studio').BrokerPosition>(
      `/v1/positions/${encodeURIComponent(positionId)}`,
    );
  }

  createExecutionReview(
    type: ExecutionActionType,
    targetId: string,
    protection?: UpdateProtectionInput,
  ) {
    return this.client.request<import('@/domain/studio').ExecutionActionReview>(
      `${executionPath(type, targetId)}-review`,
      {
        method: 'POST',
        ...(type === 'update_protection' ? { body: JSON.stringify(protection) } : {}),
      },
    );
  }

  confirmExecutionAction(
    type: ExecutionActionType,
    targetId: string,
    input: ConfirmExecutionActionInput,
  ) {
    return this.client.request<import('@/domain/studio').ExecutionAction>(
      executionPath(type, targetId),
      {
        method: 'POST',
        body: JSON.stringify(input),
      },
    );
  }

  getExecutionAction(actionId: string) {
    return this.client.request<import('@/domain/studio').ExecutionAction>(
      `/v1/execution-actions/${encodeURIComponent(actionId)}`,
    );
  }

  async getLatestMarketScan(environment: BrokerEnvironment) {
    try {
      return await this.client.request<import('@/domain/studio').MarketScan>(
        `/v1/market-scans/latest?environment=${encodeURIComponent(environment)}`,
      );
    } catch (error) {
      if (error instanceof SignalOSApiError && error.status === 404) return null;
      throw error;
    }
  }

  runMarketScan(environment: BrokerEnvironment) {
    return this.client.request<import('@/domain/studio').MarketScan>(
      `/v1/market-scans?environment=${encodeURIComponent(environment)}`,
      { method: 'POST' },
    );
  }

  getLatestMarketReview(environment: BrokerEnvironment) {
    return this.client.request<import('@/domain/studio').MarketReview | null>(
      `/v1/market-reviews/latest?environment=${encodeURIComponent(environment)}`,
    );
  }

  requestMarketAnalysis(environment: BrokerEnvironment) {
    return this.client.request<import('@/domain/studio').MarketAnalysisRequest>(
      `/v1/market-analysis-requests?environment=${encodeURIComponent(environment)}`,
      { method: 'POST' },
    );
  }

  getMarketAnalysisRequest(requestId: string) {
    return this.client.request<import('@/domain/studio').MarketAnalysisRequest>(
      `/v1/market-analysis-requests/${encodeURIComponent(requestId)}`,
    );
  }

  listTradeProposals(connectionId?: string) {
    return this.client.request<import('@/domain/studio').TradeProposal[]>(
      `/v1/trade-proposals${connectionId ? `?connection_id=${encodeURIComponent(connectionId)}` : ''}`,
    );
  }

  async getTradeProposal(proposalId: string) {
    try {
      return await this.client.request<import('@/domain/studio').TradeProposal>(
        `/v1/trade-proposals/${encodeURIComponent(proposalId)}`,
      );
    } catch (error) {
      if (error instanceof SignalOSApiError && error.status === 404) return null;
      throw error;
    }
  }

  rejectTradeProposal(proposalId: string) {
    return this.client.request<import('@/domain/studio').TradeProposal>(
      `/v1/trade-proposals/${encodeURIComponent(proposalId)}/reject`,
      { method: 'POST' },
    );
  }

  addTradeProposalFeedback(proposalId: string, input: ProposalFeedbackInput) {
    return this.client.request<void>(
      `/v1/trade-proposals/${encodeURIComponent(proposalId)}/feedback`,
      {
        method: 'POST',
        body: JSON.stringify(input),
      },
    );
  }

  createOrderReview(proposalId: string) {
    return this.client.request<import('@/domain/studio').OrderReview>(
      `/v1/trade-proposals/${encodeURIComponent(proposalId)}/order-review`,
      { method: 'POST' },
    );
  }

  submitTradeOrder(proposalId: string, input: SubmitOrderInput) {
    return this.client.request<import('@/domain/studio').BrokerOrder>(
      `/v1/trade-proposals/${encodeURIComponent(proposalId)}/submit`,
      {
        method: 'POST',
        body: JSON.stringify(input),
      },
    );
  }

  listBrokerOrders(proposalId: string) {
    return this.client.request<import('@/domain/studio').BrokerOrder[]>(
      `/v1/orders?proposal_id=${encodeURIComponent(proposalId)}`,
    );
  }

  listMemory() {
    return this.client.request<import('@/domain/studio').UserMemory[]>('/v1/me/memory');
  }

  deleteMemory(memoryId: string) {
    return this.client.request<void>(`/v1/me/memory/${encodeURIComponent(memoryId)}`, {
      method: 'DELETE',
    });
  }

  resetLearnedPreferences() {
    return this.client.request<void>('/v1/me/memory/reset-learned-preferences', { method: 'POST' });
  }
}
