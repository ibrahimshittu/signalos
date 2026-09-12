import { describe, expect, it, jest } from '@jest/globals';
import { HttpIntelligenceApi } from './intelligence';

function response(body: unknown): Response {
  return { ok: true, status: 202, json: jest.fn(async () => body) } as unknown as Response;
}

describe('HttpIntelligenceApi', () => {
  it('binds identity through a Supabase token and never trusts an account id in the body', async () => {
    const fetchImpl = jest.fn<typeof fetch>(async () => response({ id: 'run-1' }));
    const api = new HttpIntelligenceApi({
      baseUrl: 'https://api.signalos.test',
      fetchImpl,
      getHeaders: async () => ({ Authorization: 'Bearer signed-access-token' }),
    });

    await api.ask({
      question: 'What changed in the London session?',
      accountId: 'untrusted-account-id',
      contextEntityIds: ['BTCUSDT'],
      mode: 'deep',
    });

    const [, init] = fetchImpl.mock.calls[0];
    expect(init?.headers).toEqual(expect.objectContaining({ Authorization: 'Bearer signed-access-token' }));
    expect(JSON.parse(String(init?.body))).toEqual({
      question: 'What changed in the London session?',
      context_entity_ids: ['BTCUSDT'],
      mode: 'deep',
    });
  });
});
