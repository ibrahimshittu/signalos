import { describe, expect, it, jest } from '@jest/globals';
import { InvestmentProfileInput } from '@/domain/studio';
import { SignalOSApiError } from './transport';
import { HttpSignalOSApi } from './http';

const profile: InvestmentProfileInput = {
  goals: ['capital_growth'],
  intended_capital: null,
  time_horizon: 'swing',
  liquidity_need: 'moderate',
  investing_experience: 'intermediate',
  trading_experience: 'beginner',
  products_traded: ['stocks_etfs', 'crypto_spot'],
  decision_frequency: 'monthly',
  drawdown_response: 'hold',
  holding_periods: ['multi_day'],
  explanation_detail: 'standard',
  notification_frequency: 'opportunities_only',
  disclosures_accepted: true,
};

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: jest.fn(async () => body),
    text: jest.fn(async () => JSON.stringify(body)),
  } as unknown as Response;
}

describe('HttpSignalOSApi', () => {
  it('reviews and submits the exact ticket through the real execution endpoints', async () => {
    const review = {
      id: 'review-1',
      ticket: { proposal_id: 'proposal-1', proposal_hash: 'a'.repeat(64) },
    };
    const order = { id: 'order-1', proposal_id: 'proposal-1', state: 'acknowledged' };
    const fetchImpl = jest
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response(review, 201))
      .mockResolvedValueOnce(response(order, 202))
      .mockResolvedValueOnce(response([order]));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer verified-session' }),
    });
    await expect(api.createOrderReview('proposal-1')).resolves.toEqual(review);
    const input = {
      review_id: review.id,
      proposal_hash: review.ticket.proposal_hash,
      idempotency_key: 'signalos:proposal-1',
    };
    await expect(api.submitTradeOrder('proposal-1', input)).resolves.toEqual(order);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      'https://api.signalos.test/v1/trade-proposals/proposal-1/order-review',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      'https://api.signalos.test/v1/trade-proposals/proposal-1/submit',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(input),
        headers: expect.objectContaining({ Authorization: 'Bearer verified-session' }),
      }),
    );
    await expect(api.listBrokerOrders('proposal-1')).resolves.toEqual([order]);
    expect(fetchImpl).toHaveBeenLastCalledWith(
      'https://api.signalos.test/v1/orders?proposal_id=proposal-1',
      expect.any(Object),
    );
  });
  it('saves the backend investment-profile contract with a Supabase access token', async () => {
    const saved = { ...profile, user_id: 'user-1' };
    const fetchImpl = jest.fn<typeof fetch>(async () => response(saved));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: async () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.saveInvestmentProfile(profile)).resolves.toEqual(saved);
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://api.signalos.test/v1/me/investment-profile',
      expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          Authorization: 'Bearer signed-access-token',
        }),
        body: JSON.stringify(profile),
      }),
    );
  });

  it('creates a human-confirmed Bybit trading connection without retaining credentials', async () => {
    const connection = { id: 'connection-1', provider_id: 'bybit', status: 'pending' };
    const fetchImpl = jest.fn<typeof fetch>(async () => response(connection, 201));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test/',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });
    const credentials = {
      provider_id: 'bybit' as const,
      environment: 'mainnet' as const,
      api_key: 'read-key',
      api_secret: 'read-secret',
    };

    await expect(api.createBrokerConnection(credentials)).resolves.toEqual(connection);
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://api.signalos.test/v1/broker-connections',
      expect.objectContaining({ method: 'POST', body: JSON.stringify(credentials) }),
    );
  });

  it('preserves structured error codes for actionable recovery UI', async () => {
    const fetchImpl = jest.fn<typeof fetch>(async () =>
      response(
        {
          code: 'bybit_environment_mismatch',
          detail: 'This key does not match the selected Bybit environment.',
        },
        422,
      ),
    );
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.verifyBrokerConnection('connection-1')).rejects.toMatchObject({
      name: 'SignalOSApiError',
      code: 'bybit_environment_mismatch',
      status: 422,
      retryable: false,
    } satisfies Partial<SignalOSApiError>);
  });

  it('loads the latest reconciled portfolio for the active broker context', async () => {
    const summary = {
      connection_id: 'connection-1',
      provider_id: 'bybit',
      environment: 'mainnet',
      total_equity: '12000.50',
    };
    const fetchImpl = jest.fn<typeof fetch>(async () => response(summary));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.getPortfolioSummary()).resolves.toEqual(summary);
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://api.signalos.test/v1/portfolio-summary',
      expect.any(Object),
    );
  });

  it('runs a manual market scan for the active environment', async () => {
    const scan = {
      id: 'scan-1',
      environment: 'mainnet',
      source_count: 426,
      result: { hot_universe: [], agent_shortlist: [] },
    };
    const fetchImpl = jest.fn<typeof fetch>(async () => response(scan, 201));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.runMarketScan('mainnet')).resolves.toEqual(scan);
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://api.signalos.test/v1/market-scans?environment=mainnet',
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('loads the latest explainable market review', async () => {
    const review = {
      scan_id: 'scan-1',
      environment: 'mainnet',
      candidates_considered: 1,
      candidates: [
        {
          category: 'linear',
          symbol: 'BTCUSDT',
          rank: 1,
          status: 'no_approved_strategy',
          reason: 'No live strategy is available for trade analysis.',
        },
      ],
    };
    const fetchImpl = jest.fn<typeof fetch>(async () => response(review));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.getLatestMarketReview('mainnet')).resolves.toEqual(review);
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://api.signalos.test/v1/market-reviews/latest?environment=mainnet',
      expect.any(Object),
    );
  });

  it('requests and tracks a fresh strategy review for the active environment', async () => {
    const analysisRequest = {
      id: 'analysis-1',
      environment: 'mainnet',
      status: 'queued',
      requested_at: '2026-08-17T09:00:00Z',
      started_at: null,
      completed_at: null,
      scan_id: null,
      error_code: null,
    };
    const fetchImpl = jest.fn<typeof fetch>(async () => response(analysisRequest, 202));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.requestMarketAnalysis('mainnet')).resolves.toEqual(analysisRequest);
    await expect(api.getMarketAnalysisRequest('analysis-1')).resolves.toEqual(analysisRequest);
    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      'https://api.signalos.test/v1/market-analysis-requests?environment=mainnet',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      'https://api.signalos.test/v1/market-analysis-requests/analysis-1',
      expect.any(Object),
    );
  });

  it('loads reconciled open positions so portfolio usage can be explained', async () => {
    const positions = [{ id: 'position-1', symbol: 'BTCUSDT', state: 'open' }];
    const fetchImpl = jest.fn<typeof fetch>(async () => response(positions));
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.listOpenPositions()).resolves.toEqual(positions);
    expect(fetchImpl).toHaveBeenCalledWith(
      'https://api.signalos.test/v1/positions?open_only=true',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer signed-access-token' }),
      }),
    );
  });

  it('accepts successful 204 responses without attempting to parse JSON', async () => {
    const json = jest.fn();
    const fetchImpl = jest.fn<typeof fetch>(
      async () =>
        ({
          ok: true,
          status: 204,
          json,
        }) as unknown as Response,
    );
    const api = new HttpSignalOSApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await expect(api.resetLearnedPreferences()).resolves.toBeUndefined();
    expect(json).not.toHaveBeenCalled();
  });
});
