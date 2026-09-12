import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

/**
 * Haptics are reserved for meaning. Ordinary buttons and navigation produce
 * nothing — feedback that fires on every tap stops carrying information.
 *
 * Every call is fire-and-forget: a failed haptic must never interrupt a
 * financial action.
 */
function fire(run: () => Promise<void>) {
  if (Platform.OS === 'web') return;
  run().catch(() => {});
}

/** Choosing an option, changing a segment. */
export const selection = () => fire(() => Haptics.selectionAsync());

/** A trade was approved, an account connected — something completed. */
export const success = () =>
  fire(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success));

/** Terms expired, data went stale, a gate blocked the action. */
export const warning = () =>
  fire(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning));

/** The action was rejected or failed. */
export const failure = () =>
  fire(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error));

/** Committing to a consequential action, such as opening secure approval. */
export const commit = () =>
  fire(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium));
