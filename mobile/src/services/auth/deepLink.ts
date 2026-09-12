export type AuthCallback =
  | { kind: 'none' }
  | { kind: 'error'; message: string }
  | { kind: 'code'; code: string; recovery: boolean }
  | { kind: 'session'; accessToken: string; refreshToken: string; recovery: boolean };

function callbackParams(url: string): URLSearchParams {
  const queryStart = url.indexOf('?');
  const fragmentStart = url.indexOf('#');
  const queryEnd = fragmentStart >= 0 ? fragmentStart : url.length;
  const query = queryStart >= 0 ? url.slice(queryStart + 1, queryEnd) : '';
  const fragment = fragmentStart >= 0 ? url.slice(fragmentStart + 1) : '';
  return new URLSearchParams([query, fragment].filter(Boolean).join('&'));
}

function safeDescription(value: string | null): string {
  if (!value) return 'The authentication link is invalid or has expired.';
  return value
    .replace(/[\u0000-\u001F\u007F]/g, ' ')
    .trim()
    .slice(0, 160);
}

/** Parses only SignalOS-owned auth callbacks. Other app links are ignored. */
export function authCallbackFromUrl(url: string): AuthCallback {
  if (!url.startsWith('signalos://auth/')) return { kind: 'none' };

  const params = callbackParams(url);
  if (params.has('error') || params.has('error_code')) {
    return { kind: 'error', message: safeDescription(params.get('error_description')) };
  }

  const recovery = params.get('type') === 'recovery';
  const accessToken = params.get('access_token');
  const refreshToken = params.get('refresh_token');
  if (accessToken && refreshToken) {
    return { kind: 'session', accessToken, refreshToken, recovery };
  }

  const code = params.get('code');
  return code ? { kind: 'code', code, recovery } : { kind: 'none' };
}
