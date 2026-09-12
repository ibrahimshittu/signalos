import { describe, expect, it } from '@jest/globals';
import { authCallbackFromUrl } from './deepLink';

describe('authCallbackFromUrl', () => {
  it('extracts an implicit session from a native callback fragment', () => {
    expect(
      authCallbackFromUrl(
        'signalos://auth/callback#access_token=access&refresh_token=refresh&type=signup',
      ),
    ).toEqual({
      kind: 'session',
      accessToken: 'access',
      refreshToken: 'refresh',
      recovery: false,
    });
  });

  it('recognizes a PKCE authorization code and recovery intent', () => {
    expect(authCallbackFromUrl('signalos://auth/recovery?code=abc123&type=recovery')).toEqual({
      kind: 'code',
      code: 'abc123',
      recovery: true,
    });
  });

  it('turns provider errors into a safe callback error', () => {
    expect(
      authCallbackFromUrl(
        'signalos://auth/callback?error_code=otp_expired&error_description=Email%20link%20expired',
      ),
    ).toEqual({ kind: 'error', message: 'Email link expired' });
  });

  it('ignores unrelated links', () => {
    expect(authCallbackFromUrl('signalos://market/BTCUSDT')).toEqual({ kind: 'none' });
  });
});
