import { useCallback, useState } from 'react';
import { Stack, router, useLocalSearchParams } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { HeaderButton } from '@/components/navigation/HeaderButton';
import { profileSteps } from '@/components/onboarding/questions';
import { Button, FlowScreen, OptionRow, Progress, Reveal, Text } from '@/components/ui';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

/**
 * The investment profile, one question per screen.
 *
 * It is deliberately provider-agnostic: nothing here mentions a broker, and no
 * question asks the user to set a stop, a position size, or a leverage — those
 * belong to the risk engine and are shown back as a derived mandate instead.
 */
export default function ProfileScreen() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const reviewing = mode === 'review';

  const draft = useAppStore((state) => state.profileDraft);
  const setDraft = useAppStore((state) => state.setProfileDraft);
  const [index, setIndex] = useState(0);

  const step = profileSteps[index];
  const selected = step.selected(draft);
  const canContinue = step.complete(draft);

  const goBack = useCallback(() => {
    if (index > 0) setIndex((value) => value - 1);
    else if (router.canGoBack()) router.back();
  }, [index]);

  const goNext = useCallback(() => {
    if (index < profileSteps.length - 1) setIndex((value) => value + 1);
    else if (reviewing) router.push({ pathname: '/mandate', params: { mode: 'review' } });
    else router.push('/mandate');
  }, [index, reviewing]);

  return (
    <>
      <Stack.Screen
        options={{
          gestureEnabled: false,
          headerLeft: () => <HeaderButton label="Back" onPress={goBack} symbol="chevron.left" />,
        }}
      />
      <FlowScreen
        footer={
          <Button
            disabled={!canContinue}
            onPress={goNext}
            title={index === profileSteps.length - 1 ? 'See my starting mandate' : 'Continue'}
          />
        }
        topInset={false}>
        <Progress
          label={`${index + 1} of ${profileSteps.length}`}
          step={index + 1}
          total={profileSteps.length}
        />

        <Reveal key={step.id}>
          <Text accessibilityRole="header" style={styles.title} variant="title1">
            {step.title}
          </Text>
          <Text style={styles.body} tone="secondary" variant="callout">
            {step.body}
          </Text>

          <View accessibilityRole={step.multiple ? undefined : 'radiogroup'} style={styles.options}>
            {step.options.map((option) => (
              <OptionRow
                detail={option.detail}
                key={option.value}
                multiple={step.multiple}
                onPress={() => setDraft(step.apply(draft, option.value))}
                selected={selected.includes(option.value)}
                title={option.title}
              />
            ))}
          </View>
        </Reveal>
      </FlowScreen>
    </>
  );
}

const styles = StyleSheet.create({
  title: { marginTop: tokens.space.xl },
  body: { marginTop: tokens.space.sm, maxWidth: 480 },
  options: { marginTop: tokens.space.xl, gap: tokens.space.sm },
});
