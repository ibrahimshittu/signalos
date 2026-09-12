import { Stack } from 'expo-router';
import { rootScreenOptions, stackScreenOptions } from '@/components/navigation/options';

export default function SignalsLayout() {
  return (
    <Stack screenOptions={stackScreenOptions}>
      <Stack.Screen name="signals" options={{ ...rootScreenOptions, title: 'Signals' }} />
    </Stack>
  );
}
