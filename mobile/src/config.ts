import Constants from 'expo-constants';

function required(name: string, value: string | undefined): string {
  const normalized = value?.trim();
  if (!normalized) throw new Error(`${name} is required. Add it to mobile/.env.local.`);
  return normalized;
}

interface PublicConfigInput {
  signalosApiUrl: string | undefined;
  supabaseUrl: string | undefined;
  supabasePublishableKey: string | undefined;
  /** Metro host advertised by Expo, for example `192.168.1.125:8081`. */
  developmentHostUri?: string;
  isDevelopment?: boolean;
}

const loopbackHosts = new Set(['127.0.0.1', 'localhost', '::1']);

function hostnameFromHostUri(hostUri: string | undefined): string | null {
  if (!hostUri?.trim()) return null;
  try {
    return new URL(hostUri.includes('://') ? hostUri : `http://${hostUri}`).hostname;
  } catch {
    return null;
  }
}

/**
 * A physical phone resolves loopback to itself, not to the Mac running FastAPI.
 * During an Expo development session we can safely borrow Metro's LAN host
 * while preserving the backend port configured by the developer.
 */
function resolveApiUrl(value: string, developmentHostUri?: string, isDevelopment = false): string {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error('EXPO_PUBLIC_SIGNALOS_API_URL must be a valid HTTP(S) URL.');
  }

  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error('EXPO_PUBLIC_SIGNALOS_API_URL must use HTTP or HTTPS.');
  }

  if (!loopbackHosts.has(url.hostname)) return url.toString().replace(/\/$/, '');
  if (!isDevelopment) {
    throw new Error('EXPO_PUBLIC_SIGNALOS_API_URL cannot use a loopback host in production.');
  }

  const developmentHost = hostnameFromHostUri(developmentHostUri);
  if (developmentHost && !loopbackHosts.has(developmentHost)) url.hostname = developmentHost;
  return url.toString().replace(/\/$/, '');
}

export function resolvePublicConfig(input: PublicConfigInput) {
  const signalosApiUrl = resolveApiUrl(
    required('EXPO_PUBLIC_SIGNALOS_API_URL', input.signalosApiUrl),
    input.developmentHostUri,
    input.isDevelopment,
  );
  const supabaseUrl = required('EXPO_PUBLIC_SUPABASE_URL', input.supabaseUrl);
  const supabasePublishableKey = required(
    'EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
    input.supabasePublishableKey,
  );

  if (!supabaseUrl.startsWith('https://')) {
    throw new Error('EXPO_PUBLIC_SUPABASE_URL must use HTTPS.');
  }

  if (!supabasePublishableKey.startsWith('sb_publishable_')) {
    throw new Error('EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY must be a Supabase publishable key.');
  }

  return { signalosApiUrl, supabaseUrl, supabasePublishableKey };
}

const publicConfig = resolvePublicConfig({
  signalosApiUrl: process.env.EXPO_PUBLIC_SIGNALOS_API_URL,
  supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL,
  supabasePublishableKey: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
  developmentHostUri:
    Constants.expoConfig?.hostUri ?? Constants.expoGoConfig?.debuggerHost ?? undefined,
  isDevelopment: __DEV__,
});

export const SIGNALOS_API_URL = publicConfig.signalosApiUrl;
export const SUPABASE_URL = publicConfig.supabaseUrl;
export const SUPABASE_PUBLISHABLE_KEY = publicConfig.supabasePublishableKey;

export const SIGNALOS_AUTH_REDIRECT_URL = 'signalos://auth/callback';
export const SIGNALOS_PASSWORD_RECOVERY_URL = 'signalos://auth/recovery';
