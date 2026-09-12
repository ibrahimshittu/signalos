import { router, useLocalSearchParams } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { MandateSummary } from '@/components/profile/MandateSummary';
import { Button, Callout, EmptyState, FlowScreen, Text } from '@/components/ui';
import { deriveAdaptiveMandate } from '@/domain/mandate';
import { toProfileInput } from '@/domain/profile';
import * as haptics from '@/lib/haptics';
import { useSaveInvestmentProfile } from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

/**
 * The result of the profile: a mandate the system derived, explained in the
 * user's own answers.
 *
 * The copy is careful never to imply the user designed the risk engine. They
 * described themselves; SignalOS chose the ceilings.
 */
export default function MandateScreen() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const reviewing = mode === 'review';

  const draft = useAppStore((state) => state.profileDraft);
  const save = useSaveInvestmentProfile();
  const input = toProfileInput(draft);

  if (!input) {
    return (
      <FlowScreen topInset={false}>
        <EmptyState
          action={{ title: 'Back to questions', onPress: () => router.replace('/profile') }}
          body="A mandate is only calculated once every question has an answer."
          symbol="questionmark.circle"
          title="Your profile is not complete yet"
        />
      </FlowScreen>
    );
  }

  const mandate = deriveAdaptiveMandate(input);

  const saveAndReturn = () => {
    save.mutate(
      { ...input, disclosures_accepted: true },
      {
        onSuccess: () => {
          haptics.success();
          router.dismissTo('/account');
        },
      },
    );
  };

  return (
    <FlowScreen
      footer={
        <View style={styles.footer}>
          <Button
            loading={save.isPending}
            onPress={reviewing ? saveAndReturn : () => router.push('/disclosures')}
            title={reviewing ? 'Save changes' : 'Continue to disclosures'}
          />
          <Button
            onPress={() =>
              reviewing
                ? router.replace({ pathname: '/profile', params: { mode: 'review' } })
                : router.replace('/profile')
            }
            title="Change my answers"
            variant="tertiary"
          />
        </View>
      }
      topInset={false}>
      <Text accessibilityRole="header" variant="title1">
        Your starting mandate
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        SignalOS built this from what you told us. It adapts before every proposal, using your connected portfolio,
        current market conditions, liquidity, execution costs, and platform policy.
      </Text>

      <View style={styles.mandate}>
        <MandateSummary mandate={mandate} />
      </View>

      <Callout
        body="Position size, stop distance, target, reward-to-risk, and leverage are calculated per opportunity. You review the exact numbers before anything can happen — you never have to set them."
        style={styles.callout}
        title="Sizing stays with the system"
      />

      {save.isError ? (
        <Callout
          body={save.error instanceof Error ? save.error.message : 'Your profile could not be saved.'}
          live
          style={styles.callout}
          title="Nothing was saved"
          tone="caution"
        />
      ) : null}
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  lede: { marginTop: tokens.space.sm, maxWidth: 480 },
  mandate: { marginTop: tokens.space.xl },
  callout: { marginTop: tokens.space.xl },
  footer: { gap: tokens.space.xs },
});
