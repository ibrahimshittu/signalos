import { useEffect } from 'react';
import { AppState, Platform } from 'react-native';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useToast } from '@/components/ui';
import { useAppStore } from '@/store/useAppStore';
import { studioKeys } from '@/query/studioHooks';
import { nativeNotifications, proposalFromNotification, pushProjectId, registerPush } from './push';

export function usePushNotifications() {
  const userId = useAppStore((state) => state.ownerUserId);
  const ready = useAppStore(
    (state) => state.restoredUserId === state.ownerUserId && state.hasOnboarded,
  );
  const client = useQueryClient();
  const { showToast } = useToast();

  useEffect(() => {
    if (!userId || !ready || Platform.OS === 'web' || !pushProjectId()) return;
    let active = true;
    let refreshing = false;
    const subscriptions: { remove(): void }[] = [];
    async function refresh() {
      if (!active || refreshing) return;
      refreshing = true;
      try {
        await registerPush(userId!);
      } catch {
        if (active)
          showToast({
            tone: 'error',
            title: 'Notifications need attention',
            message: 'Open Account → Notifications to reconnect this device.',
          });
      } finally {
        refreshing = false;
      }
    }
    void (async () => {
      try {
        const notifications = nativeNotifications();
        if (!active) return;
        const open = (data: Record<string, unknown> | undefined) => {
          const id = proposalFromNotification(data ?? {});
          if (!id || !active || useAppStore.getState().ownerUserId !== userId) return;
          router.push({ pathname: '/trade-proposal/[id]', params: { id } });
          void notifications.clearLastNotificationResponseAsync().catch(() => {});
        };
        subscriptions.push(
          notifications.addNotificationResponseReceivedListener((response) =>
            open(response.notification.request.content.data),
          ),
          notifications.addNotificationReceivedListener(() => {
            void client.invalidateQueries({ queryKey: studioKeys.all });
          }),
          notifications.addPushTokenListener(() => {
            void refresh();
          }),
          AppState.addEventListener('change', (state) => {
            if (state === 'active') void refresh();
          }),
        );
        const response = notifications.getLastNotificationResponse();
        if (response) open(response.notification.request.content.data);
        await refresh();
      } catch {
        if (active)
          showToast({
            tone: 'error',
            title: 'Notification setup incomplete',
            message: 'Rebuild SignalOS with push support, then enable notifications in Account.',
          });
      }
    })();
    return () => {
      active = false;
      subscriptions.forEach((subscription) => subscription.remove());
    };
  }, [client, ready, showToast, userId]);
}
