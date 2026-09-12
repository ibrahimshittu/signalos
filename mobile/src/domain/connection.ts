import type { BrokerConnection, ConnectionStatus } from './studio';

export interface ConnectionHealth {
  label: string;
  tone: 'neutral' | 'active' | 'positive' | 'caution' | 'critical';
  /** What this means for the user, in plain language. */
  meaning: string;
  /** True when the user has to do something before the studio can work. */
  needsAttention: boolean;
}

const states: Record<ConnectionStatus, ConnectionHealth> = {
  pending: {
    label: 'Pending',
    tone: 'neutral',
    meaning: 'The credential has been stored but not yet checked.',
    needsAttention: false,
  },
  verifying: {
    label: 'Verifying',
    tone: 'active',
    meaning: 'Checking the key’s permissions and account identity.',
    needsAttention: false,
  },
  syncing: {
    label: 'Syncing',
    tone: 'active',
    meaning: 'Reading balances and positions for the first time.',
    needsAttention: false,
  },
  healthy: {
    label: 'Connected',
    tone: 'positive',
    meaning: 'Balances and positions are reading normally.',
    needsAttention: false,
  },
  degraded: {
    label: 'Degraded',
    tone: 'caution',
    meaning: 'Some reads are failing, so figures may be behind.',
    needsAttention: true,
  },
  failed: {
    label: 'Disconnected',
    tone: 'critical',
    meaning: 'SignalOS cannot read this account. Nothing can be proposed.',
    needsAttention: true,
  },
  revoked: {
    label: 'Revoked',
    tone: 'critical',
    meaning: 'The key was revoked at the provider. Reconnect to continue.',
    needsAttention: true,
  },
};

const NOT_CONNECTED: ConnectionHealth = {
  label: 'Not connected',
  tone: 'caution',
  meaning: 'Connect a provider so proposals can be sized against real capital.',
  needsAttention: true,
};

export function connectionHealth(connection: BrokerConnection | null | undefined): ConnectionHealth {
  return connection ? states[connection.status] : NOT_CONNECTED;
}

/** Display name for a provider id. */
export function providerName(id: string | undefined): string {
  return id === 'bybit' ? 'Bybit' : (id ?? 'Provider');
}

export function environmentName(environment: 'mainnet' | 'testnet'): string {
  return environment === 'mainnet' ? 'Mainnet' : 'Testnet';
}

/** Bybit keys and secrets contain no whitespace; pasted formatting is discarded. */
export function normalizeBrokerCredential(value: string): string {
  return value.replace(/\s/g, '');
}
