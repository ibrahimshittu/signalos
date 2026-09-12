import { useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, Callout, FlowScreen, OptionRow, Text } from '@/components/ui';
import { toProfileInput } from '@/domain/profile';
import { useSaveInvestmentProfile } from '@/query/studioHooks';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

const agreements = [
  {
    id: 'market',
    title: 'Markets can lose money',
    detail: 'Crypto and derivatives can fall sharply. Leverage accelerates losses, including full liquidation.',
  },
  {
    id: 'analysis',
    title: 'Analysis is not a guarantee',
    detail: 'Research, agent reasoning, and backtests can all fail in live markets. No trade is a normal outcome.',
  },
  {
    id: 'control',
    title: 'Approval is always yours',
    detail: 'SignalOS may prepare a proposal, but it cannot place or cancel an order without your exact confirmation.',
  },
] as const;

export default function DisclosuresScreen() {
  const draft = useAppStore((state) => state.profileDraft);
  const save = useSaveInvestmentProfile();
  const [accepted, setAccepted] = useState<string[]>([]);
  const allAccepted = accepted.length === agreements.length;

  const toggle = (id: string) =>
    setAccepted((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));

  const submit = () => {
    const input = toProfileInput(draft);
    if (!input || !allAccepted) return;
    save.mutate({ ...input, disclosures_accepted: true }, { onSuccess: () => router.push('/connect') });
  };

  return (
    <FlowScreen
      footer={
        <Button
          disabled={!allAccepted}
          loading={save.isPending}
          onPress={submit}
          title="Accept and continue"
        />
      }
      topInset={false}>
      <Text accessibilityRole="header" variant="title1">
        Before you connect an account
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        Acknowledge each of these. They describe how SignalOS behaves, and what it will never do.
      </Text>

      <View style={styles.agreements}>
        {agreements.map((agreement) => (
          <OptionRow
            detail={agreement.detail}
            key={agreement.id}
            multiple
            onPress={() => toggle(agreement.id)}
            selected={accepted.includes(agreement.id)}
            title={agreement.title}
          />
        ))}
      </View>

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
  agreements: { marginTop: tokens.space.xl, gap: tokens.space.sm },
  callout: { marginTop: tokens.space.xl },
});
