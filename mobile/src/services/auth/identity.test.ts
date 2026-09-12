import { describe, expect, it } from '@jest/globals';
import { accountFromUser, publicAuthError } from './identity';

describe('accountFromUser', () => {
  it('uses verified Supabase identity metadata', () => {
    expect(
      accountFromUser({
        email: 'alex@example.com',
        user_metadata: { first_name: 'Alex', last_name: 'Example' },
      }),
    ).toEqual({ firstName: 'Alex', lastName: 'Example', email: 'alex@example.com' });
  });

  it('never serializes unexpected metadata values into the UI', () => {
    expect(
      accountFromUser({
        email: 'user@example.com',
        user_metadata: { first_name: { unsafe: true }, last_name: 42 },
      }),
    ).toEqual({ firstName: '', lastName: '', email: 'user@example.com' });
  });
});

describe('publicAuthError', () => {
  it('keeps expected authentication feedback useful', () => {
    expect(publicAuthError({ message: 'Invalid login credentials' })).toBe(
      'The email or password is incorrect.',
    );
  });

  it('does not expose unexpected provider internals', () => {
    expect(publicAuthError({ message: 'database connection string leaked' })).toBe(
      'Authentication could not be completed. Please try again.',
    );
  });

  it('uses stable Supabase codes for actionable authentication feedback', () => {
    expect(publicAuthError({ code: 'invalid_credentials', message: 'changed copy' })).toBe(
      'The email or password is incorrect.',
    );
    expect(publicAuthError({ code: 'over_email_send_rate_limit' })).toBe(
      'Too many emails were requested. Wait a few minutes and try again.',
    );
    expect(publicAuthError({ code: 'request_timeout' })).toBe(
      'Supabase took too long to respond. Check your connection and try again.',
    );
  });

  it('explains when hosted email delivery is not configured for an address', () => {
    expect(publicAuthError({ code: 'email_address_not_authorized' })).toBe(
      'SignalOS cannot send a confirmation email to this address yet. Use an approved test address or configure custom SMTP.',
    );
  });

  it('distinguishes a device network failure from rejected credentials', () => {
    expect(publicAuthError({ name: 'AuthRetryableFetchError', message: 'Network request failed' })).toBe(
      'SignalOS could not reach Supabase. Check your internet connection and try again.',
    );
  });
});
