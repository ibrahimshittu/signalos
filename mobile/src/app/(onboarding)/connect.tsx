import { useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import {
  Button,
  Callout,
  EmptyState,
  ErrorState,
  Field,
  FlowScreen,
  LoadingBlock,
  ProviderMark,
  Segmented,
  Text,
  useToast,
} from '@/components/ui';
import { normalizeBrokerCredential } from '@/domain/connection';
import type { BrokerEnvironment } from '@/domain/studio';
import * as haptics from '@/lib/haptics';
import {
  useBrokerProviders,
  useCreateBrokerConnection,
  useDisconnectBroker,
  useSwitchBrokerContext,
  useSyncBrokerConnection,
  useVerifyBrokerConnection,
} from '@/query/studioHooks';
import { SignalOSApiError } from '@/services/api/transport';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

const environments = [
  { value: 'mainnet' as const, label: 'Live' },
  { value: 'testnet' as const, label: 'Testnet' },
];

interface ConnectionIssue {
  title: string;
  body: string;
}

function connectionIssue(error: unknown, environment: BrokerEnvironment): ConnectionIssue {
  if (error instanceof SignalOSApiError && error.code === 'bybit_environment_mismatch') {
    const account = environment === 'mainnet' ? 'Live' : 'Testnet';
    return {
      title: `This key does not match Bybit ${account}`,
      body:
        environment === 'testnet'
          ? 'Demo Trading and Testnet are separate Bybit environments. Create the key in Bybit Testnet, then paste its matching secret.'
          : 'Create the key in your live Bybit account, then paste the matching key and secret.',
    };
  }
  return {
    title: 'Bybit could not be connected',
    body:
      error instanceof Error
        ? error.message
        : 'Check the key, secret, and selected account, then try again.',
  };
}

/**
 * The only provider-specific screen in onboarding, and the last one.
 *
 * The investment profile is already complete by this point, so adding another
 * provider later never means answering the questionnaire again.
 */
export default function ConnectScreen() {
  const providers = useBrokerProviders();
  const completeOnboarding = useAppStore((state) => state.completeOnboarding);
  const { showToast } = useToast();

  const [environment, setEnvironment] = useState<BrokerEnvironment>('mainnet');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [issue, setIssue] = useState<ConnectionIssue | null>(null);
  const activeProvider =
    providers.data?.find((provider) => provider.id === 'bybit' && provider.status === 'enabled') ??
    null;

  const create = useCreateBrokerConnection();
  const disconnect = useDisconnectBroker();
  const verify = useVerifyBrokerConnection();
  const sync = useSyncBrokerConnection();
  const switchContext = useSwitchBrokerContext();

  const pending =
    create.isPending ||
    disconnect.isPending ||
    verify.isPending ||
    sync.isPending ||
    switchContext.isPending;
  const stage = create.isPending
    ? 'Securing your credentials'
    : verify.isPending
      ? 'Checking the account and permissions'
      : sync.isPending
        ? 'Synchronizing your portfolio'
        : switchContext.isPending
          ? 'Preparing your studio'
          : null;

  const connect = async () => {
    if (!activeProvider) return;
    setIssue(null);
    let connectionId: string | null = null;
    try {
      const connection = await create.mutateAsync({
        provider_id: activeProvider.id,
        environment,
        api_key: normalizeBrokerCredential(apiKey),
        api_secret: normalizeBrokerCredential(apiSecret),
      });
      connectionId = connection.id;
      // The credential is consumed by the request and never held in state.
      setApiKey('');
      setApiSecret('');
      await verify.mutateAsync(connection.id);
      await sync.mutateAsync(connection.id);
      await switchContext.mutateAsync({ connectionId: connection.id, environment });
      completeOnboarding();
      haptics.success();
      showToast({
        title: 'Bybit connected',
        message: 'Your balances and positions are synchronized.',
        tone: 'success',
      });
      router.replace('/studio');
    } catch (caught) {
      setApiKey('');
      setApiSecret('');
      if (connectionId) {
        await disconnect.mutateAsync(connectionId).catch(() => undefined);
      }
      haptics.failure();
      const nextIssue = connectionIssue(caught, environment);
      setIssue(nextIssue);
      showToast({ title: 'Connection needs attention', message: nextIssue.title, tone: 'error' });
    }
  };

  return (
    <FlowScreen
      footer={
        activeProvider ? (
          <Button
            disabled={!normalizeBrokerCredential(apiKey) || !normalizeBrokerCredential(apiSecret)}
            loading={pending}
            onPress={connect}
            title="Connect Bybit"
          />
        ) : undefined
      }
      topInset={false}
    >
      <Text accessibilityRole="header" variant="title1">
        Connect a provider
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        Link a trading account to sync your portfolio and prepare orders you approve.
      </Text>

      {providers.isLoading ? <LoadingBlock lines={2} /> : null}
      {providers.isError && !activeProvider ? (
        <ErrorState
          body="Check your connection, then try loading your providers again."
          onRetry={() => void providers.refetch()}
          retrying={providers.isRefetching}
          title="Providers could not be loaded"
        />
      ) : null}
      {providers.isSuccess && !activeProvider ? (
        <EmptyState
          body="No trading provider is available right now. Your profile is saved."
          symbol="link"
          title="Connection is unavailable"
          action={{
            title: 'Check again',
            onPress: () => void providers.refetch(),
            loading: providers.isRefetching,
          }}
        />
      ) : null}

      {activeProvider ? (
        <View style={styles.form}>
          <View style={styles.providerSection}>
            <Text tone="secondary" variant="subhead">
              Provider
            </Text>
            <View style={styles.providerIdentity}>
              <ProviderMark
                displayName={activeProvider.display_name}
                providerId={activeProvider.id}
                size={44}
              />
              <Text variant="title3">{activeProvider.display_name}</Text>
            </View>
          </View>

          {activeProvider.supported_environments.length > 1 ? (
            <View style={styles.section}>
              <Text variant="title3">Account environment</Text>
              <Segmented
                label="Account environment"
                onChange={setEnvironment}
                options={environments.filter((option) =>
                  activeProvider.supported_environments.includes(option.value),
                )}
                value={environment}
              />
              <Text tone="tertiary" variant="footnote">
                Choose where this API key was created. Bybit Demo Trading is separate from Testnet.
              </Text>
            </View>
          ) : null}

          <View style={styles.credentials}>
            <Text variant="title3">API credentials</Text>
            <Callout
              body="Enable Orders for Spot and/or Derivatives. Keep withdrawals and transfers off."
              title="Required permissions"
            />
            <Field
              autoCapitalize="none"
              label="API key"
              onChangeText={(value) => setApiKey(normalizeBrokerCredential(value))}
              placeholder="Paste API key"
              value={apiKey}
            />
            <Field
              autoCapitalize="none"
              label="API secret"
              onChangeText={(value) => setApiSecret(normalizeBrokerCredential(value))}
              placeholder="Paste the secret"
              secureTextEntry
              value={apiSecret}
            />
          </View>

          {stage ? (
            <Text accessibilityLiveRegion="polite" tone="accent" variant="subhead">
              {stage}…
            </Text>
          ) : null}
          {issue ? <Callout body={issue.body} live title={issue.title} tone="caution" /> : null}
        </View>
      ) : null}
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  lede: { marginTop: tokens.space.sm, maxWidth: 480 },
  form: { gap: tokens.space.xxl, marginTop: tokens.space.xxl },
  providerSection: { gap: tokens.space.sm },
  providerIdentity: {
    minHeight: tokens.layout.touch,
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.md,
  },
  section: { gap: tokens.space.sm },
  credentials: { gap: tokens.space.lg },
});
