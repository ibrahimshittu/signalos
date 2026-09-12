import { Stack } from 'expo-router';
import { rootScreenOptions, stackScreenOptions } from '@/components/navigation/options';

export default function AccountLayout() {
  return (
    <Stack screenOptions={stackScreenOptions}>
      <Stack.Screen name="account" options={{ ...rootScreenOptions, title: 'Account' }} />
    </Stack>
  );
}
