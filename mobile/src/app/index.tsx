import { Redirect } from 'expo-router';
import { View } from 'react-native';
import { useAuth } from '@/services/auth/AuthProvider';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

/**
 * Entry gate. Renders nothing while rehydrating — the splash screen is still
 * covering the app at this point.
 */
export default function Index() {
  const hydrated = useAppStore((state) => state.hydrated);
  const { initializing, session } = useAuth();

  if (!hydrated || initializing) {
    return <View style={{ flex: 1, backgroundColor: tokens.color.bg.canvas }} />;
  }
  if (!session) return <Redirect href="/welcome" />;
  return <Redirect href="/studio" />;
}
