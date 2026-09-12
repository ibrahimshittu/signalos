import { Redirect } from 'expo-router';
import { NativeTabs } from 'expo-router/unstable-native-tabs';
import { Alert, View } from 'react-native';
import { Button, ErrorState, LoadingBlock } from '@/components/ui';
import { isAwaitingDecision } from '@/domain/proposal';
import { useRestoreAccount } from '@/query/studioHooks';
import { useAuth } from '@/services/auth/AuthProvider';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

/**
 * The system tab bar.
 *
 * `NativeTabs` renders the real UIKit tab bar, which is what adopts Liquid
 * Glass on iOS 26 and gives us scroll-to-top, pop-to-root, and the correct
 * content insets for free. Nothing here recreates that chrome.
 *
 * `minimizeBehavior="never"` keeps all four labels visible at all times, as the
 * tab bar is the app's only global orientation.
 */
export default function TabsLayout() {
  const hydrated = useAppStore((state) => state.hydrated);
  const hasOnboarded = useAppStore((state) => state.hasOnboarded);
  const restoredUserId = useAppStore((state) => state.restoredUserId);
  const profile = useAppStore((state) => state.investmentProfile);
  const awaiting = useAppStore((state) => state.tradeProposals.filter(isAwaitingDecision).length);
  const { initializing, session, signOut } = useAuth();
  const needsRestore = Boolean(session && restoredUserId !== session.user.id);
  const restoration = useRestoreAccount(
    session?.user.id,
    hydrated && !initializing && needsRestore,
  );

  if (!hydrated || initializing) return null;
  if (!session) return <Redirect href="/welcome" />;
  if (needsRestore)
    return (
      <View
        style={{
          flex: 1,
          padding: tokens.layout.gutter,
          paddingTop: 80,
          backgroundColor: tokens.color.bg.canvas,
        }}
      >
        {restoration.isError ? (
          <>
            <ErrorState
              title="Could not restore your account"
              body="Your saved profile is still on SignalOS. Retry to reconnect."
              onRetry={() => void restoration.refetch()}
              retrying={restoration.isFetching}
            />
            <Button
              title="Sign out"
              variant="tertiary"
              onPress={() =>
                void signOut().catch(() =>
                  Alert.alert('Could not sign out', 'Check your connection and try again.'),
                )
              }
            />
          </>
        ) : (
          <LoadingBlock />
        )}
      </View>
    );
  if (!hasOnboarded)
    return (
      <Redirect
        href={!profile ? '/profile' : !profile.disclosures_accepted ? '/disclosures' : '/connect'}
      />
    );

  return (
    <NativeTabs
      badgeBackgroundColor={tokens.color.accent.base}
      minimizeBehavior="never"
      tintColor={tokens.color.accent.base}
    >
      <NativeTabs.Trigger name="(studio)">
        <NativeTabs.Trigger.Icon
          md="pie_chart"
          sf={{ default: 'chart.pie', selected: 'chart.pie.fill' }}
        />
        <NativeTabs.Trigger.Label>Studio</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="(signals)">
        <NativeTabs.Trigger.Icon md="monitor_heart" sf="waveform.path.ecg" />
        <NativeTabs.Trigger.Label>Signals</NativeTabs.Trigger.Label>
        {/* A factual count of items needing review — not a nudge to trade.
            The element is omitted entirely at zero: `hidden` still renders the
            badge, so an empty queue showed a "0" that read like a score. */}
        {awaiting > 0 ? (
          <NativeTabs.Trigger.Badge>{String(awaiting)}</NativeTabs.Trigger.Badge>
        ) : null}
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="(markets)">
        <NativeTabs.Trigger.Icon md="show_chart" sf="chart.line.uptrend.xyaxis" />
        <NativeTabs.Trigger.Label>Markets</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>

      <NativeTabs.Trigger name="(account)">
        <NativeTabs.Trigger.Icon md="person" sf={{ default: 'person', selected: 'person.fill' }} />
        <NativeTabs.Trigger.Label>Account</NativeTabs.Trigger.Label>
      </NativeTabs.Trigger>
    </NativeTabs>
  );
}
