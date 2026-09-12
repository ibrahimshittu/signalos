import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export interface SecureStorageBackend {
  getItemAsync(key: string): Promise<string | null>;
  setItemAsync(key: string, value: string): Promise<void>;
  deleteItemAsync(key: string): Promise<void>;
}

interface StorageManifest {
  version: 1;
  chunkVersion: string;
  chunkCount: number;
}

interface ChunkedStorageOptions {
  chunkSize?: number;
  createVersion?: () => string;
}

const DEFAULT_CHUNK_SIZE = 1_800;

function safeKey(key: string): string {
  return key.replace(/[^A-Za-z0-9._-]/g, '_');
}

function manifestKey(key: string): string {
  return `signalos.${safeKey(key)}.manifest`;
}

function chunkKey(key: string, version: string, index: number): string {
  return `signalos.${safeKey(key)}.chunk.${safeKey(version)}.${index}`;
}

function parseManifest(value: string | null): StorageManifest | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as Partial<StorageManifest>;
    if (
      parsed.version === 1 &&
      typeof parsed.chunkVersion === 'string' &&
      parsed.chunkVersion.length > 0 &&
      Number.isInteger(parsed.chunkCount) &&
      Number(parsed.chunkCount) > 0
    ) {
      return parsed as StorageManifest;
    }
  } catch {
    // A malformed manifest is treated as no session, never as token material.
  }
  return null;
}

async function deleteChunks(backend: SecureStorageBackend, key: string, manifest: StorageManifest) {
  await Promise.all(
    Array.from({ length: manifest.chunkCount }, (_, index) =>
      backend.deleteItemAsync(chunkKey(key, manifest.chunkVersion, index)),
    ),
  );
}

export function createChunkedSecureStorage(
  backend: SecureStorageBackend,
  options: ChunkedStorageOptions = {},
) {
  const chunkSize = options.chunkSize ?? DEFAULT_CHUNK_SIZE;
  const createVersion =
    options.createVersion ?? (() => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`);

  if (!Number.isInteger(chunkSize) || chunkSize <= 0) throw new Error('chunkSize must be positive.');

  return {
    async getItem(key: string): Promise<string | null> {
      const manifest = parseManifest(await backend.getItemAsync(manifestKey(key)));
      if (!manifest) return null;

      const chunks = await Promise.all(
        Array.from({ length: manifest.chunkCount }, (_, index) =>
          backend.getItemAsync(chunkKey(key, manifest.chunkVersion, index)),
        ),
      );
      if (chunks.some((chunk) => chunk === null)) return null;
      return chunks.join('');
    },

    async setItem(key: string, value: string): Promise<void> {
      const previous = parseManifest(await backend.getItemAsync(manifestKey(key)));
      const chunkVersion = createVersion();
      const chunks = value.match(new RegExp(`.{1,${chunkSize}}`, 'gs')) ?? [''];
      const next: StorageManifest = { version: 1, chunkVersion, chunkCount: chunks.length };

      await Promise.all(
        chunks.map((chunk, index) => backend.setItemAsync(chunkKey(key, chunkVersion, index), chunk)),
      );
      // The manifest is the commit point. An interrupted write cannot expose a partial new session.
      await backend.setItemAsync(manifestKey(key), JSON.stringify(next));
      if (previous) await deleteChunks(backend, key, previous);
    },

    async removeItem(key: string): Promise<void> {
      const manifest = parseManifest(await backend.getItemAsync(manifestKey(key)));
      await backend.deleteItemAsync(manifestKey(key));
      if (manifest) await deleteChunks(backend, key, manifest);
    },
  };
}

const nativeBackend: SecureStorageBackend = {
  getItemAsync: (key) =>
    SecureStore.getItemAsync(key, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      keychainService: 'com.signalos.app.auth',
    }),
  setItemAsync: (key, value) =>
    SecureStore.setItemAsync(key, value, {
      keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      keychainService: 'com.signalos.app.auth',
    }),
  deleteItemAsync: (key) =>
    SecureStore.deleteItemAsync(key, {
      keychainService: 'com.signalos.app.auth',
    }),
};

const browserBackend: SecureStorageBackend = {
  getItemAsync: (key) => AsyncStorage.getItem(key),
  setItemAsync: (key, value) => AsyncStorage.setItem(key, value),
  deleteItemAsync: (key) => AsyncStorage.removeItem(key),
};

/** Static rendering must not persist or attempt to read a browser session. */
const serverBackend: SecureStorageBackend = {
  getItemAsync: async () => null,
  setItemAsync: async () => undefined,
  deleteItemAsync: async () => undefined,
};

function runtimeBackend(): SecureStorageBackend {
  if (Platform.OS !== 'web') return nativeBackend;
  return typeof window === 'undefined' ? serverBackend : browserBackend;
}

export const secureSessionStorage = createChunkedSecureStorage(runtimeBackend());
