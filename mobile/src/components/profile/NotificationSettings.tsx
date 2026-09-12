import { useState } from 'react';
import { Linking, View } from 'react-native';
import { useMutation } from '@tanstack/react-query';
import { Button, Section, Text } from '@/components/ui';
import { useAppStore } from '@/store/useAppStore';
import { disablePush, pushProjectId, registerPush } from '@/services/notifications/push';
import { tokens } from '@/theme/tokens';

export function NotificationSettings() {
  const userId = useAppStore((state) => state.ownerUserId);
  const [message, setMessage] = useState<string | null>(null);
  const change = useMutation({
    mutationFn: async (enabled: boolean) => {
      if (!userId) throw new Error('Sign in before changing notifications.');
      if (enabled) await registerPush(userId, true);
      else await disablePush(userId);
      return enabled;
    },
    onSuccess: (enabled) =>
      setMessage(
        enabled
          ? 'This device is registered. Delivery also requires the notification worker and platform credentials.'
          : 'Proposal notifications are off on this device.',
      ),
  });
  return (
    <Section
      title="Notifications"
      caption="New proposals only. Nothing is traded from a notification."
    >
      <View style={{ gap: tokens.space.md, marginTop: tokens.space.base }}>
        {!pushProjectId() ? (
          <Text tone="secondary" variant="footnote">
            Push setup is not complete for this build. An Expo project and platform credentials are
            required.
          </Text>
        ) : (
          <>
            <Button
              title="Enable on this device"
              variant="secondary"
              loading={change.isPending}
              onPress={() => change.mutate(true)}
            />
            <Button
              title="Turn off on this device"
              variant="tertiary"
              disabled={change.isPending}
              onPress={() => change.mutate(false)}
            />
          </>
        )}
        {change.isError ? (
          <Text tone="loss" variant="footnote">
            {change.error.message}
          </Text>
        ) : message ? (
          <Text tone="secondary" variant="footnote">
            {message}
          </Text>
        ) : null}
        <Button
          title="Open device settings"
          variant="tertiary"
          size="compact"
          onPress={() =>
            void Linking.openSettings().catch(() =>
              setMessage('Open Settings on your device, then find SignalOS.'),
            )
          }
        />
      </View>
    </Section>
  );
}
