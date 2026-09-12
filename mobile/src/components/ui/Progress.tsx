import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

interface Props {
  step: number;
  total: number;
  label?: string;
}

/**
 * Flow progress.
 *
 * The fill animates with `scaleX` rather than width, so advancing a step runs
 * on the compositor and never triggers a layout pass. It holds still under
 * Reduce Motion.
 */
export function Progress({ label, step, total }: Props) {
  const reduceMotion = useReducedMotion();
  const ratio = Math.min(1, Math.max(0, step / total));
  const progress = useSharedValue(ratio);

  useEffect(() => {
    progress.set(
      reduceMotion
        ? ratio
        : withTiming(ratio, {
            duration: tokens.motion.duration.state,
            easing: Easing.bezier(...tokens.motion.easing.out),
          }),
    );
  }, [progress, ratio, reduceMotion]);

  const fill = useAnimatedStyle(() => ({ transform: [{ scaleX: progress.value }] }));

  return (
    <View
      accessibilityRole="progressbar"
      accessibilityValue={{ min: 0, max: total, now: step }}
      style={styles.wrap}>
      <View style={styles.track}>
        <Animated.View style={[styles.fill, fill]} />
      </View>
      <Text numeric tone="tertiary" variant="caption">
        {label ?? `Step ${step} of ${total}`}
      </Text>
    </View>
  );
}

const HEIGHT = 4;

const styles = StyleSheet.create({
  wrap: { gap: tokens.space.sm },
  track: {
    height: HEIGHT,
    borderRadius: tokens.radius.full,
    backgroundColor: tokens.color.bg.sunken,
    overflow: 'hidden',
  },
  fill: {
    height: HEIGHT,
    backgroundColor: tokens.color.accent.base,
    borderRadius: tokens.radius.full,
    transformOrigin: 'left',
  },
});
