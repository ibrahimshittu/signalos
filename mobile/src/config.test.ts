import { describe, expect, it } from '@jest/globals';
import * as config from './config';

describe('mobile runtime configuration', () => {
  it('exposes only the live API and public Supabase client configuration', () => {
    expect(config.SIGNALOS_API_URL).toBe('https://api.signalos.test');
    expect(config.SUPABASE_URL).toBe('https://project.supabase.co');
    expect(config.SUPABASE_PUBLISHABLE_KEY).toBe('sb_publishable_test');
    expect(config.SIGNALOS_AUTH_REDIRECT_URL).toBe('signalos://auth/callback');
    expect(config).not.toHaveProperty('USE_MOCK_API');
    expect(config).not.toHaveProperty('SIGNALOS_DEVELOPMENT_USER_ID');
  });

  it('fails closed when the publishable key is missing', () => {
    expect(() =>
      config.resolvePublicConfig({
        signalosApiUrl: 'https://api.signalos.test',
        supabaseUrl: 'https://project.supabase.co',
        supabasePublishableKey: undefined,
      }),
    ).toThrow('EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY');
  });

  it('maps a loopback API URL to the Expo host on a physical development device', () => {
    expect(
      config.resolvePublicConfig({
        signalosApiUrl: 'http://127.0.0.1:8001',
        supabaseUrl: 'https://project.supabase.co',
        supabasePublishableKey: 'sb_publishable_test',
        developmentHostUri: '192.168.1.125:8081',
        isDevelopment: true,
      }).signalosApiUrl,
    ).toBe('http://192.168.1.125:8001');
  });

  it('rejects loopback API URLs in production builds', () => {
    expect(() =>
      config.resolvePublicConfig({
        signalosApiUrl: 'http://localhost:8001',
        supabaseUrl: 'https://project.supabase.co',
        supabasePublishableKey: 'sb_publishable_test',
        isDevelopment: false,
      }),
    ).toThrow('loopback');
  });
});
