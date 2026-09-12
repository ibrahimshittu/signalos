import { useCallback, useState } from 'react';
import { router } from 'expo-router';
import { Alert, StyleSheet, View } from 'react-native';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { MandateSummary } from '@/components/profile/MandateSummary';
import { NotificationSettings } from '@/components/profile/NotificationSettings';
import {
  Avatar,
  Button,
  Callout,
  Card,
  CardRow,
  ProviderMark,
  Screen,
  Section,
  StatusBadge,
  Tag,
  Text,
} from '@/components/ui';
import { connectionHealth, environmentName, providerName } from '@/domain/connection';
import { useDisconnectBroker, useMemory, useResetLearnedPreferences } from '@/query/studioHooks';
import { useAuth } from '@/services/auth/AuthProvider';
import { useAppStore } from '@/store/useAppStore';
import { formatRatioPct, formatRelativeIso } from '@/lib/format';
import { tokens } from '@/theme/tokens';

export default function AccountScreen() {
  const account = useAppStore((state) => state.account);
  const connection = useAppStore((state) => state.brokerConnection);
  const profile = useAppStore((state) => state.investmentProfile);
  const [showLimits, setShowLimits] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const { signOut } = useAuth();

  const memory = useMemory();
  const resetPreferences = useResetLearnedPreferences();
  const disconnect = useDisconnectBroker();

  const health = connectionHealth(connection);
  const learned = (memory.data ?? []).filter((item) => item.kind === 'learned_preference');
  const provider = providerName(connection?.provider_id);

  const confirmDisconnect = useCallback(() => {
    if (!connection) return;
    Alert.alert(
      'Disconnect this provider?',
      'SignalOS stops reading balances and withdraws every open proposal. Your provider account and its positions are untouched.',
      [
        { text: 'Keep connected', style: 'cancel' },
        {
          text: 'Disconnect',
          style: 'destructive',
          onPress: () =>
            disconnect.mutate(connection.id, { onSuccess: () => router.replace('/connect') }),
        },
      ],
    );
  }, [connection, disconnect]);

  return (
    <Screen>
      <View style={styles.identity}>
        <Avatar firstName={account.firstName} lastName={account.lastName} size={52} />
        <View style={styles.identityCopy}>
          <Text variant="title3">
            {account.firstName || account.lastName
              ? `${account.firstName} ${account.lastName}`.trim()
              : 'SignalOS investor'}
          </Text>
          <Text style={styles.email} tone="tertiary" variant="footnote">
            {account.email || 'Signed in to SignalOS'}
          </Text>
        </View>
      </View>

      <Section level="primary" title="Connection">
        <Card style={styles.card}>
          <CardRow
            emphasis
            label={provider}
            last={!connection}
            leading={
              <ProviderMark
                displayName={provider}
                providerId={connection?.provider_id ?? 'unknown'}
              />
            }
          >
            <View style={styles.provider}>
              {connection ? (
                <Tag
                  label={environmentName(connection.environment)}
                  tone={connection.environment === 'mainnet' ? 'accent' : 'neutral'}
                />
              ) : null}
              <StatusBadge label={health.label} tone={health.tone} />
            </View>
          </CardRow>
          {connection ? (
            <>
              <CardRow label="Account UID" value={connection.external_uid ?? 'Not verified'} />
              <CardRow
                label="Last sync"
                numeric={false}
                value={formatRelativeIso(connection.last_synced_at)}
              />
              <CardRow
                label="Permissions"
                last
                numeric={false}
                value={
                  connection.spot_trading_enabled && connection.derivatives_trading_enabled
                    ? 'Spot and derivatives orders'
                    : connection.derivatives_trading_enabled
                      ? 'Derivatives orders'
                      : connection.spot_trading_enabled
                        ? 'Spot orders'
                        : 'Pending verification'
                }
              />
            </>
          ) : null}
        </Card>

        <Text style={styles.meaning} tone="secondary" variant="footnote">
          {health.meaning}
        </Text>

        {connection ? (
          <Button
            loading={disconnect.isPending}
            onPress={confirmDisconnect}
            size="compact"
            style={styles.action}
            title="Disconnect provider"
            variant="destructive"
          />
        ) : (
          <Button
            onPress={() => router.push('/connect')}
            size="compact"
            style={styles.action}
            title="Connect a provider"
            variant="secondary"
          />
        )}
      </Section>

      <Section title="Your preferences">
        <Card style={styles.card}>
          <CardRow
            emphasis
            label="Investment profile"
            detail="Goals, experience and time horizon"
            onPress={() => router.push({ pathname: '/profile', params: { mode: 'review' } })}
          />
          <CardRow
            emphasis
            label="Personalized preferences"
            detail="Markets, holding periods and explanations"
            last
            onPress={() => router.push('/personalization')}
          />
        </Card>
      </Section>

      <Section
        title="Safety limits"
        caption={
          profile
            ? `Per trade: up to ${formatRatioPct(profile.adaptive_mandate.max_loss_per_trade_pct)} risk · ${profile.adaptive_mandate.max_leverage}× leverage`
            : 'Complete your profile to establish your limits.'
        }
        action={
          <HeaderButton
            label={showLimits ? 'Hide' : 'Details'}
            showLabel
            onPress={() => setShowLimits(!showLimits)}
          />
        }
      >
        {showLimits && profile ? (
          <View style={styles.card}>
            <MandateSummary mandate={profile.adaptive_mandate} showExplanation={false} />
          </View>
        ) : null}
      </Section>

      <NotificationSettings />

      {learned.length ? (
        <Section
          caption="What SignalOS has inferred from how you decide."
          title={`Learned preferences · ${learned.length}`}
        >
          <Text style={styles.card} tone="secondary" variant="callout">
            Reset these inferences without changing your investment profile.
          </Text>
          <Button
            disabled={learned.length === 0}
            loading={resetPreferences.isPending}
            onPress={() =>
              Alert.alert(
                'Reset learned preferences?',
                'Your investment profile and safety limits will stay unchanged.',
                [
                  { text: 'Cancel', style: 'cancel' },
                  { text: 'Reset', style: 'destructive', onPress: () => resetPreferences.mutate() },
                ],
              )
            }
            size="compact"
            style={styles.action}
            title="Reset learned preferences"
            variant="secondary"
          />
        </Section>
      ) : null}

      <Section title="Security">
        <Callout
          body="Every order needs recent authentication and your confirmation. Withdrawals and transfers are never permitted."
          style={styles.card}
          title="You authorize every order"
        />
      </Section>

      <View style={styles.session}>
        <Button
          loading={signingOut}
          onPress={() => {
            setSigningOut(true);
            void signOut()
              .then(() => router.replace('/welcome'))
              .catch(() =>
                Alert.alert('Could not sign out', 'Check your connection and try again.'),
              )
              .finally(() => setSigningOut(false));
          }}
          title="Sign out"
          variant="secondary"
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  identity: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.base,
    paddingTop: tokens.space.xs,
  },
  identityCopy: { flex: 1 },
  email: { marginTop: tokens.optical.tick },
  card: { marginTop: tokens.space.base },
  provider: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    alignItems: 'center',
    gap: tokens.space.sm,
    flexShrink: 1,
  },
  meaning: { marginTop: tokens.space.md },
  action: { alignSelf: 'flex-start', marginTop: tokens.space.base },
  session: { marginTop: tokens.space.xxxl, gap: tokens.space.sm },
});
