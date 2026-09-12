import { Stack } from 'expo-router';
import { rootScreenOptions, stackScreenOptions } from '@/components/navigation/options';

export default function MarketsLayout() {
  return (
    <Stack screenOptions={stackScreenOptions}>
      <Stack.Screen name="markets" options={{ ...rootScreenOptions, title: 'Markets' }} />
    </Stack>
  );
}
