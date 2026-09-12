import { SIGNALOS_API_URL } from '@/config';
import { signalOSAuthorizationHeaders } from '@/services/auth/supabase';

export class SignalOSApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryable: boolean,
    readonly code?: string,
  ) {
    super(message);
    this.name = 'SignalOSApiError';
  }
}

export interface SignalOSHttpOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
  getHeaders?: () => Record<string, string> | Promise<Record<string, string>>;
  timeoutMs?: number;
}

function errorMessage(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
  }
  return 'SignalOS could not complete this request.';
}

function errorCode(body: unknown): string | undefined {
  if (body && typeof body === 'object' && 'code' in body) {
    const code = (body as { code: unknown }).code;
    if (typeof code === 'string') return code;
  }
  return undefined;
}

export class SignalOSHttpClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly getHeaders: () => Record<string, string> | Promise<Record<string, string>>;
  private readonly timeoutMs: number;

  constructor(options: SignalOSHttpOptions = {}) {
    this.baseUrl = (options.baseUrl ?? SIGNALOS_API_URL).replace(/\/$/, '');
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.getHeaders = options.getHeaders ?? signalOSAuthorizationHeaders;
    this.timeoutMs = options.timeoutMs ?? 20_000;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const identityHeaders = await this.getHeaders();
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...init,
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...identityHeaders,
          ...init.headers,
        },
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new SignalOSApiError(
          errorMessage(body),
          response.status,
          response.status === 429 || response.status >= 500,
          errorCode(body),
        );
      }
      if (response.status === 204) return undefined as T;
      return await response.json() as T;
    } catch (error) {
      if (error instanceof SignalOSApiError) throw error;
      throw new SignalOSApiError(
        error instanceof Error && error.name === 'AbortError'
          ? 'SignalOS is taking longer than expected.'
          : 'SignalOS could not reach the investment service.',
        0,
        true,
      );
    } finally {
      clearTimeout(timeout);
    }
  }
}
