import { type PropsWithChildren } from 'react';
import {
  Pressable,
  StyleSheet,
  View,
  type GestureResponderEvent,
  type PressableProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { tokens } from '@/theme/tokens';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

/**
 * `scale` for standalone controls, `highlight` for full-width rows — scaling a
 * row that spans the screen reads as a glitch — and `opacity` for inline links.
 */
export type PressFeedback = 'scale' | 'highlight' | 'opacity' | 'none';

export type TouchableProps = PropsWithChildren<
  Omit<PressableProps, 'style'> & {
    style?: StyleProp<ViewStyle>;
    feedback?: PressFeedback;
    /** Matches the highlight to the shape of the row it sits behind. */
    highlightRadius?: number;
  }
>;

/**
 * Press feedback begins on touch-down, animates transform and opacity only,
 * and collapses to a plain opacity change under Reduce Motion.
 *
 * The press lands quickly and releases a little slower, so a tap reads as
 * pressure applied and let go rather than as a snap.
 */
export function Touchable({
  children,
  disabled,
  feedback = 'scale',
  highlightRadius = tokens.radius.md,
  onPressIn,
  onPressOut,
  style,
  ...rest
}: TouchableProps) {
  const reduceMotion = useReducedMotion();
  const pressed = useSharedValue(0);

  const animatedStyle = useAnimatedStyle(() => {
    if (feedback === 'none' || feedback === 'highlight') return {};
    if (reduceMotion || feedback === 'opacity') return { opacity: 1 - pressed.value * 0.4 };
    return { transform: [{ scale: 1 - pressed.value * (1 - tokens.motion.pressScale) }] };
  });

  const highlightStyle = useAnimatedStyle(() => ({ opacity: pressed.value }));

  const press = (value: number, duration: number) => (event: GestureResponderEvent) => {
    if (!disabled) {
      pressed.set(
        withTiming(value, { duration, easing: Easing.bezier(...tokens.motion.easing.out) }),
      );
    }
    (value ? onPressIn : onPressOut)?.(event);
  };

  return (
    <AnimatedPressable
      {...rest}
      disabled={disabled}
      onPressIn={press(1, tokens.motion.duration.pressIn)}
      onPressOut={press(0, tokens.motion.duration.pressOut)}
      style={[style, animatedStyle]}>
      {feedback === 'highlight' ? (
        <Animated.View
          pointerEvents="none"
          style={[
            StyleSheet.absoluteFill,
            styles.highlight,
            { borderRadius: highlightRadius },
            highlightStyle,
          ]}
        />
      ) : null}
      {children}
    </AnimatedPressable>
  );
}

/** Guarantees the 44pt touch minimum around visually smaller controls. */
export function TouchTarget({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  return <View style={[styles.target, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  highlight: { backgroundColor: tokens.color.bg.sunken, borderCurve: 'continuous' },
  target: {
    minWidth: tokens.layout.touch,
    minHeight: tokens.layout.touch,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
