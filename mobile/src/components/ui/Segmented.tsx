import { useCallback, useRef, useState } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withTiming,
} from 'react-native-reanimated';
import { Text } from './Text';
import { Touchable } from './Touchable';
import * as haptics from '@/lib/haptics';
import { tokens } from '@/theme/tokens';

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  options: SegmentOption<T>[];
  value: T;
  /** `NoInfer` keeps the state setter from widening `T` back to `string`. */
  onChange(value: NoInfer<T>): void;
  /** Names the group for assistive technology, e.g. "Proposal filter". */
  label: string;
}

const INSET = 3;
const GAP = tokens.optical.nudge;

/**
 * A filter across a small, fixed set.
 *
 * The thumb travels to the segment you picked rather than teleporting, which
 * is what makes the control read as one object with a moving highlight instead
 * of three that light up independently. It moves on `translateX` alone, so the
 * whole transition runs on the compositor and never triggers layout.
 *
 * Selection changes weight and colour but never type size — a size change
 * would reflow the label and make the control twitch on every tap. Under
 * Reduce Motion the thumb jumps, and the selection is still unambiguous.
 */
export function Segmented<T extends string>({ label, onChange, options, value }: Props<T>) {
  const reduceMotion = useReducedMotion();
  const [trackWidth, setTrackWidth] = useState(0);
  const offset = useSharedValue(0);
  // The first measure positions the thumb; only later changes are travelled.
  const measured = useRef(false);

  const count = options.length;
  const segmentWidth = trackWidth > 0 ? (trackWidth - INSET * 2 - GAP * (count - 1)) / count : 0;
  const index = Math.max(0, options.findIndex((option) => option.value === value));

  const moveTo = useCallback(
    (position: number, width: number) => {
      const next = INSET + position * (width + GAP);
      if (!measured.current || reduceMotion) {
        offset.set(next);
        measured.current = true;
        return;
      }
      offset.set(
        withTiming(next, {
          duration: tokens.motion.duration.state,
          easing: Easing.bezier(...tokens.motion.easing.out),
        }),
      );
    },
    [offset, reduceMotion],
  );

  const onLayout = useCallback(
    (event: LayoutChangeEvent) => {
      const width = event.nativeEvent.layout.width;
      if (width === trackWidth) return;
      setTrackWidth(width);
      measured.current = false;
      moveTo(index, (width - INSET * 2 - GAP * (count - 1)) / count);
    },
    [count, index, moveTo, trackWidth],
  );

  const thumbStyle = useAnimatedStyle(() => ({ transform: [{ translateX: offset.value }] }));

  return (
    <View
      accessibilityLabel={label}
      accessibilityRole="tablist"
      onLayout={onLayout}
      style={styles.track}>
      {segmentWidth > 0 ? (
        <Animated.View
          pointerEvents="none"
          style={[styles.thumb, { width: segmentWidth }, thumbStyle]}
        />
      ) : null}

      {options.map((option, position) => {
        const selected = option.value === value;
        return (
          <Touchable
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            feedback="none"
            key={option.value}
            onPress={() => {
              if (selected) return;
              haptics.selection();
              moveTo(position, segmentWidth);
              onChange(option.value);
            }}
            style={styles.segment}>
            <Text
              center
              style={selected ? styles.selectedLabel : undefined}
              tone={selected ? 'primary' : 'secondary'}
              variant="subhead">
              {option.label}
            </Text>
          </Touchable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: 'row',
    gap: GAP,
    padding: INSET,
    borderRadius: tokens.radius.xl,
    borderCurve: 'continuous',
    backgroundColor: tokens.color.bg.sunken,
  },
  thumb: {
    position: 'absolute',
    top: INSET,
    bottom: INSET,
    left: 0,
    // One inset inside the track, so the two curves stay concentric.
    borderRadius: tokens.radius.xl - INSET,
    borderCurve: 'continuous',
    backgroundColor: tokens.color.bg.surface,
    boxShadow: '0 1px 3px rgba(16,24,40,0.10), 0 1px 1px rgba(16,24,40,0.04)',
  },
  segment: {
    flex: 1,
    minHeight: tokens.layout.touch - INSET * 2,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: tokens.space.sm,
  },
  selectedLabel: { fontWeight: '600' },
});
