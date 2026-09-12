import { Redirect, Stack } from 'expo-router';
import { stackScreenOptions } from '@/components/navigation/options';
import { useAuth } from '@/services/auth/AuthProvider';
import { useAppStore } from '@/store/useAppStore';

export default function ModalLayout() {
  const hydrated = useAppStore((state) => state.hydrated);
  const hasOnboarded = useAppStore((state) => state.hasOnboarded);
  const restoredUserId = useAppStore((state) => state.restoredUserId);
  const { initializing, session } = useAuth();

  if (!hydrated || initializing) return null;
  if (!session) return <Redirect href="/welcome" />;
  if (restoredUserId !== session.user.id || !hasOnboarded) return <Redirect href="/studio" />;

  // The modal keeps a native header so its glass chrome, title, and close
  // affordance behave exactly like the rest of the system.
  return <Stack screenOptions={stackScreenOptions} />;
}
