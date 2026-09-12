import { useEffect } from 'react';
import { DefaultTheme, router, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { QueryProvider } from '@/query/QueryProvider';
import { ToastProvider } from '@/components/ui';
import { AuthProvider, useAuth } from '@/services/auth/AuthProvider';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';
import { usePushNotifications } from '@/services/notifications/usePushNotifications';

SplashScreen.preventAutoHideAsync().catch(() => {});

/**
 * Keeps native chrome — headers, back gestures, tab bar — on the same palette
 * as the app. Without it, header buttons flicker when switching tabs.
 */
const navigationTheme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: tokens.color.accent.base,
    background: tokens.color.bg.canvas,
    card: tokens.color.bg.canvas,
    text: tokens.color.text.primary,
    border: tokens.color.border.hairline,
  },
};

function AppNavigation() {
  usePushNotifications();
  const hydrated = useAppStore((state) => state.hydrated);
  const { clearRecoveryRequest, initializing, recoveryRequested } = useAuth();

  // The splash stays up until persisted session state is available, so the app
  // never flashes a signed-out screen at someone who is already signed in.
  useEffect(() => {
    if (hydrated && !initializing) SplashScreen.hideAsync().catch(() => {});
  }, [hydrated, initializing]);

  useEffect(() => {
    if (!initializing && recoveryRequested) {
      clearRecoveryRequest();
      router.replace('/reset-password');
    }
  }, [clearRecoveryRequest, initializing, recoveryRequested]);

  return (
    <ThemeProvider value={navigationTheme}>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: tokens.color.bg.canvas },
        }}
      >
        <Stack.Screen name="(onboarding)" />
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="(modals)" options={{ presentation: 'modal' }} />
      </Stack>
    </ThemeProvider>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: tokens.color.bg.canvas }}>
      <SafeAreaProvider>
        <QueryProvider>
          <ToastProvider>
            <AuthProvider>
              <AppNavigation />
            </AuthProvider>
          </ToastProvider>
        </QueryProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
