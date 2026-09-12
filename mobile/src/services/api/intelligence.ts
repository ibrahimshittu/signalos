import {
  IntelligenceEvent,
  IntelligenceQuestion,
  IntelligenceReport,
  IntelligenceRun,
} from '@/domain/intelligence';
import { SignalOSHttpClient, SignalOSHttpOptions } from './transport';

export { SignalOSApiError } from './transport';

export class HttpIntelligenceApi {
  private readonly client: SignalOSHttpClient;

  constructor(options: SignalOSHttpOptions = {}) {
    this.client = new SignalOSHttpClient(options);
  }

  ask(input: IntelligenceQuestion): Promise<IntelligenceRun> {
    return this.client.request('/v1/intelligence/questions', {
      method: 'POST',
      body: JSON.stringify({
        question: input.question,
        context_entity_ids: input.contextEntityIds ?? [],
        mode: input.mode ?? 'fast',
      }),
    });
  }

  getRun(runId: string): Promise<IntelligenceRun> {
    return this.client.request(`/v1/intelligence/runs/${encodeURIComponent(runId)}`);
  }

  getEvents(runId: string): Promise<IntelligenceEvent[]> {
    return this.client.request(`/v1/intelligence/questions/${encodeURIComponent(runId)}/events`);
  }

  getReport(reportId: string): Promise<IntelligenceReport> {
    return this.client.request(`/v1/intelligence/reports/${encodeURIComponent(reportId)}`);
  }
}

export const intelligenceApi = new HttpIntelligenceApi();
