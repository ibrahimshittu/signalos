import { describe, expect, it, jest } from '@jest/globals';
import { createChunkedSecureStorage, type SecureStorageBackend } from './secureStorage';

function memoryBackend(): SecureStorageBackend & { values: Map<string, string> } {
  const values = new Map<string, string>();
  return {
    values,
    getItemAsync: jest.fn(async (key: string) => values.get(key) ?? null),
    setItemAsync: jest.fn(async (key: string, value: string) => {
      values.set(key, value);
    }),
    deleteItemAsync: jest.fn(async (key: string) => {
      values.delete(key);
    }),
  };
}

describe('chunked secure session storage', () => {
  it('round-trips sessions larger than a native secure-store value', async () => {
    const backend = memoryBackend();
    const storage = createChunkedSecureStorage(backend, { chunkSize: 8, createVersion: () => 'v1' });
    const session = 'a secure session larger than one chunk';

    await storage.setItem('auth-token', session);

    await expect(storage.getItem('auth-token')).resolves.toBe(session);
    expect([...backend.values.keys()].filter((key) => key.includes('.chunk.'))).toHaveLength(5);
  });

  it('replaces a session atomically and removes superseded chunks', async () => {
    const backend = memoryBackend();
    const versions = ['v1', 'v2'];
    const storage = createChunkedSecureStorage(backend, {
      chunkSize: 8,
      createVersion: () => versions.shift()!,
    });

    await storage.setItem('auth-token', 'first session value');
    await storage.setItem('auth-token', 'new');

    await expect(storage.getItem('auth-token')).resolves.toBe('new');
    expect([...backend.values.keys()].some((key) => key.includes('.v1.'))).toBe(false);
  });

  it('removes the manifest and every encrypted chunk on sign-out', async () => {
    const backend = memoryBackend();
    const storage = createChunkedSecureStorage(backend, { chunkSize: 8, createVersion: () => 'v1' });
    await storage.setItem('auth-token', 'session value');

    await storage.removeItem('auth-token');

    expect(backend.values.size).toBe(0);
    await expect(storage.getItem('auth-token')).resolves.toBeNull();
  });
});
