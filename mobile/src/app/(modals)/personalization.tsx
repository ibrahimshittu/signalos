import { useState } from 'react';
import { Stack } from 'expo-router';
import { Alert, StyleSheet, View } from 'react-native';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  ErrorState,
  Field,
  LoadingBlock,
  OptionRow,
  Screen,
  Section,
  Segmented,
  Text,
  useToast,
} from '@/components/ui';
import type { PersonalizedPreferences, PersonalizedPreferencesUpdate } from '@/domain/studio';
import { getStudioApi } from '@/services/api';
import { useAppStore } from '@/store/useAppStore';
import { studioKeys } from '@/query/studioHooks';
import { tokens } from '@/theme/tokens';

const groups = [
  {
    key: 'preferred_markets',
    title: 'Markets to prioritize',
    values: ['spot', 'linear'],
    min: 1,
    max: 2,
  },
  {
    key: 'preferred_strategy_families',
    title: 'Strategy preferences',
    values: [
      'trend',
      'momentum',
      'mean_reversion',
      'breakout',
      'session',
      'volatility',
      'funding_carry',
      'microstructure',
    ],
    min: 1,
    max: 5,
  },
  {
    key: 'preferred_sessions',
    title: 'Sessions',
    values: ['tokyo', 'london', 'new_york', 'utc_rollover', 'funding'],
    min: 0,
    max: 5,
  },
  {
    key: 'holding_periods',
    title: 'Holding windows',
    values: ['intraday', 'multi_day', 'multi_week', 'long_term'],
    min: 1,
    max: 4,
  },
] as const;
const labels: Record<string, string> = {
  spot: 'Spot',
  linear: 'Perpetuals',
  new_york: 'New York',
  utc_rollover: 'UTC rollover',
  intraday: 'Same day',
  multi_day: 'Several days',
  multi_week: 'Several weeks',
  long_term: 'Long term',
};

export default function PersonalizationScreen() {
  const owner = useAppStore((state) => state.ownerUserId);
  const key = [...studioKeys.profile(), owner, 'personalization'];
  const client = useQueryClient();
  const { showToast } = useToast();
  const [draft, setDraft] = useState<PersonalizedPreferencesUpdate>({});
  const query = useQuery({
    queryKey: key,
    queryFn: () => getStudioApi().getPersonalization(),
    enabled: Boolean(owner),
  });
  const save = useMutation({
    mutationFn: () =>
      getStudioApi().updatePersonalization({
        ...draft,
        ...(draft.avoid_conditions
          ? {
              avoid_conditions: draft.avoid_conditions.map((value) => value.trim()).filter(Boolean),
            }
          : {}),
      }),
    onSuccess: (policy) => {
      client.setQueryData(key, policy);
      setDraft({});
      showToast({ title: 'Preferences saved', tone: 'success' });
    },
  });
  const generate = useMutation({
    mutationFn: () => getStudioApi().generatePersonalization(),
    onSuccess: (policy) => {
      client.setQueryData(key, policy);
      setDraft({});
    },
  });
  const preferences = query.data ? { ...query.data.preferences, ...draft } : null;
  const error = save.error ?? generate.error;
  const busy = save.isPending || generate.isPending;
  function toggle(group: (typeof groups)[number], value: string) {
    if (!preferences || busy) return;
    const current = preferences[group.key] as string[];
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    if (next.length < group.min || next.length > group.max) return;
    setDraft((previous) => ({ ...previous, [group.key]: next }));
  }
  function regenerate() {
    Alert.alert(
      'Regenerate preferences?',
      'This replaces your edits using your saved onboarding answers. Safety limits do not change.',
      [
        { text: 'Keep preferences', style: 'cancel' },
        { text: 'Regenerate', onPress: () => generate.mutate() },
      ],
    );
  }
  return (
    <>
      <Stack.Screen options={{ title: 'Personalized preferences' }} />
      <Screen>
        {query.isLoading ? (
          <LoadingBlock />
        ) : query.isError ? (
          <ErrorState onRetry={() => void query.refetch()} />
        ) : preferences ? (
          <>
            <Section
              title="Your investment focus"
              level="primary"
              caption={
                query.data?.source === 'ai_generated'
                  ? 'Generated with AI from your answers'
                  : query.data?.source === 'user_edited'
                    ? 'Edited by you'
                    : 'Based on your answers · AI fallback'
              }
            >
              <Text variant="callout">{preferences.investor_summary}</Text>
              <Text tone="secondary" variant="footnote">
                These preferences inform analysis. They cannot raise your safety limits or authorize
                trades.
              </Text>
            </Section>
            {groups.map((group) => (
              <Section
                key={group.key}
                title={group.title}
                caption={
                  group.key === 'preferred_strategy_families'
                    ? 'Choose up to five. Availability still depends on strategy validation.'
                    : undefined
                }
              >
                <View style={styles.options}>
                  {group.values.map((value) => (
                    <OptionRow
                      key={value}
                      title={
                        labels[value] ??
                        value.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
                      }
                      multiple
                      selected={(preferences[group.key] as string[]).includes(value)}
                      onPress={() => toggle(group, value)}
                    />
                  ))}
                </View>
              </Section>
            ))}
            <Section title="Explanation detail">
              <Segmented
                label="Explanation detail"
                options={[
                  { value: 'concise', label: 'Brief' },
                  { value: 'standard', label: 'Standard' },
                  { value: 'detailed', label: 'Detailed' },
                ]}
                value={preferences.explanation_detail}
                onChange={(value: PersonalizedPreferences['explanation_detail']) => {
                  if (!busy) setDraft({ ...draft, explanation_detail: value });
                }}
              />
            </Section>
            <Section
              title="Conditions to avoid"
              caption="Up to six short conditions, separated by commas."
            >
              <Field
                label="Avoid conditions"
                value={preferences.avoid_conditions.join(',')}
                onChangeText={(value) => {
                  if (!busy) setDraft({ ...draft, avoid_conditions: value.split(',').slice(0, 6) });
                }}
              />
            </Section>
            <View style={styles.actions}>
              {error ? <Text tone="loss">{error.message}</Text> : null}
              <Button
                title="Save preferences"
                loading={save.isPending}
                disabled={busy || !Object.keys(draft).length}
                onPress={() => save.mutate()}
              />
              <Button
                title="Regenerate from my answers"
                variant="tertiary"
                disabled={busy}
                loading={generate.isPending}
                onPress={regenerate}
              />
            </View>
          </>
        ) : (
          <Section title="Build your preferences">
            <Button
              title="Generate preferences"
              loading={generate.isPending}
              onPress={() => generate.mutate()}
            />
            {error ? <Text tone="loss">{error.message}</Text> : null}
          </Section>
        )}
      </Screen>
    </>
  );
}
const styles = StyleSheet.create({
  options: { gap: tokens.space.sm, marginTop: tokens.space.base },
  actions: { gap: tokens.space.base, marginTop: tokens.space.lg },
});
