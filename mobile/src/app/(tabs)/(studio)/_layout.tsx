import { Stack } from 'expo-router';
import { stackScreenOptions } from '@/components/navigation/options';

/**
 * Studio uses an inline title rather than a large one: the portfolio value is
 * the screen's headline, and two competing display-size elements would blunt it.
 */
export default function StudioLayout() {
  return (
    <Stack screenOptions={stackScreenOptions}>
      <Stack.Screen name="studio" options={{ title: 'Studio' }} />
    </Stack>
  );
}
