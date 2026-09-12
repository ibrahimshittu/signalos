import type { Account } from '@/store/useAppStore';

interface SupabaseIdentity {
  email?: string;
  user_metadata?: Record<string, unknown>;
}

function metadataText(value: unknown): string {
  return typeof value === 'string' ? value.trim().slice(0, 100) : '';
}

export function accountFromUser(user: SupabaseIdentity): Account {
  return {
    firstName: metadataText(user.user_metadata?.first_name),
    lastName: metadataText(user.user_metadata?.last_name),
    email: user.email?.trim().toLowerCase() ?? '',
  };
}

const messagesByCode: Record<string, string> = {
  invalid_credentials: 'The email or password is incorrect.',
  email_not_confirmed: 'Confirm your email before signing in.',
  user_already_exists: 'An account already exists for this email.',
  email_exists: 'An account already exists for this email.',
  weak_password: 'Use a stronger password and try again.',
  otp_expired: 'This verification code or link has expired. Request a new one.',
  mfa_verification_failed:
    'That authenticator code was not accepted. Enter the current six-digit code.',
  mfa_challenge_expired: 'This authentication check expired. Enter a new code and try again.',
  over_request_rate_limit: 'Too many attempts. Wait a few minutes and try again.',
  over_email_send_rate_limit: 'Too many emails were requested. Wait a few minutes and try again.',
  email_provider_disabled: 'New account registration is temporarily unavailable.',
  signup_disabled: 'New account registration is temporarily unavailable.',
  request_timeout: 'Supabase took too long to respond. Check your connection and try again.',
  email_address_not_authorized:
    'SignalOS cannot send a confirmation email to this address yet. Use an approved test address or configure custom SMTP.',
};

const messagesByPattern: [RegExp, string][] = [
  [/invalid login credentials/i, 'The email or password is incorrect.'],
  [/email not confirmed/i, 'Confirm your email before signing in.'],
  [/user already registered/i, 'An account already exists for this email.'],
  [/password should be at least/i, 'Use a stronger password and try again.'],
  [
    /otp.*expired|token.*expired/i,
    'This verification code or link has expired. Request a new one.',
  ],
  [/invalid.*otp|token.*invalid/i, 'The verification code is invalid. Check it and try again.'],
  [/rate limit|too many requests/i, 'Too many attempts. Wait a moment and try again.'],
  [/signup.*disabled/i, 'New account registration is temporarily unavailable.'],
  [
    /network request failed|failed to fetch|network.*error/i,
    'SignalOS could not reach Supabase. Check your internet connection and try again.',
  ],
];

function errorText(error: unknown, key: 'code' | 'message' | 'name'): string {
  if (typeof error !== 'object' || error === null || !(key in error)) return '';
  const value = (error as Record<string, unknown>)[key];
  return typeof value === 'string' ? value : '';
}

/** Maps provider errors to intentional copy without exposing backend details. */
export function publicAuthError(error: unknown): string {
  const code = errorText(error, 'code');
  if (messagesByCode[code]) return messagesByCode[code];

  const message = errorText(error, 'message');
  const name = errorText(error, 'name');
  return (
    messagesByPattern.find(([pattern]) => pattern.test(`${name} ${message}`))?.[1] ??
    'Authentication could not be completed. Please try again.'
  );
}
