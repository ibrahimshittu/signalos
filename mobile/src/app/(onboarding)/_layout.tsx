import { Stack } from 'expo-router';
import { tokens } from '@/theme/tokens';

/**
 * Onboarding keeps native headers so the back gesture, focus order, and
 * VoiceOver navigation behave as people expect. The bar sits on the canvas
 * rather than on glass: there is no content to float above yet.
 */
export default function OnboardingLayout() {
  return (
    <Stack
      screenOptions={{
        title: '',
        headerShadowVisible: false,
        headerStyle: { backgroundColor: tokens.color.bg.canvas },
        headerTintColor: tokens.color.accent.base,
        headerBackButtonDisplayMode: 'minimal',
        contentStyle: { backgroundColor: tokens.color.bg.canvas },
      }}>
      <Stack.Screen name="welcome" options={{ headerShown: false }} />
    </Stack>
  );
}
