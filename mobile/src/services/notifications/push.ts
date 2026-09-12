import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { getStudioApi } from '@/services/api';
import { useAppStore } from '@/store/useAppStore';

const registrationKey = 'signalos.push-registration';
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
interface Registration {
  userId: string;
  installationId: string;
}
let pendingRegistration: Promise<void> | null = null;

export function nativeNotifications(): typeof import('expo-notifications') {
  // Load only inside a configured native build, never while bootstrapping auth.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  return require('expo-notifications');
}

export function pushProjectId(): string | null {
  const value = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
  return typeof value === 'string' && uuid.test(value) ? value : null;
}

export function proposalFromNotification(data: Record<string, unknown>): string | null {
  return data.type === 'proposal_available' &&
    typeof data.proposal_id === 'string' &&
    uuid.test(data.proposal_id)
    ? data.proposal_id
    : null;
}

export async function pushRegistration(): Promise<Registration | null> {
  if (Platform.OS === 'web') return null;
  const raw = await SecureStore.getItemAsync(registrationKey);
  if (!raw) return null;
  try {
    const data = JSON.parse(raw) as Registration;
    return typeof data.userId === 'string' && uuid.test(data.installationId) ? data : null;
  } catch {
    return null;
  }
}

export async function disablePush(userId: string): Promise<void> {
  // Sign-out waits for an in-flight registration before revoking its token.
  await pendingRegistration?.catch(() => {});
  await revokeRegistration(userId);
}

async function revokeRegistration(userId: string): Promise<void> {
  const current = await pushRegistration();
  if (!current || current.userId !== userId) return;
  await getStudioApi().removeNotificationDevice(current.installationId);
  await SecureStore.deleteItemAsync(registrationKey);
}

// Native modules are loaded on demand so an unconfigured development build still opens.
export async function registerPush(userId: string, requestPermission = false): Promise<void> {
  if (pendingRegistration) return pendingRegistration;
  const request = registerDevice(userId, requestPermission);
  pendingRegistration = request;
  try {
    await request;
  } finally {
    if (pendingRegistration === request) pendingRegistration = null;
  }
}

async function registerDevice(userId: string, requestPermission: boolean): Promise<void> {
  const projectId = pushProjectId();
  if (!projectId)
    throw new Error('Link this build to the SignalOS Expo project before enabling notifications.');
  if (Platform.OS !== 'ios' && Platform.OS !== 'android')
    throw new Error('Enable notifications in the iOS or Android app.');
  const existing = await pushRegistration();
  if (existing && existing.userId !== userId)
    throw new Error('Sign in to the previous account and disable its notifications first.');
  if (!requestPermission && !existing) return;
  const notifications = nativeNotifications();
  if (Platform.OS === 'android')
    await notifications.setNotificationChannelAsync('default', {
      name: 'Proposals',
      importance: notifications.AndroidImportance.DEFAULT,
    });
  let permission = await notifications.getPermissionsAsync();
  if (!permission.granted && requestPermission)
    permission = await notifications.requestPermissionsAsync();
  if (!permission.granted) {
    if (existing) await revokeRegistration(userId);
    if (requestPermission)
      throw new Error(
        'Notifications are off. Allow SignalOS notifications in your device settings.',
      );
    return;
  }
  const token = await notifications.getExpoPushTokenAsync({ projectId });
  if (useAppStore.getState().ownerUserId !== userId)
    throw new Error('Your session changed. Sign in and enable notifications again.');
  // Older development builds must still reach Account to explain the required rebuild.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const crypto: typeof import('expo-crypto') = require('expo-crypto');
  const installationId = existing?.installationId ?? crypto.randomUUID();
  // Persist before the request so a lost response can be safely retried or revoked.
  await SecureStore.setItemAsync(registrationKey, JSON.stringify({ userId, installationId }));
  await getStudioApi().registerNotificationDevice(installationId, {
    platform: Platform.OS,
    expo_push_token: token.data,
    expo_project_id: projectId,
  });
}
