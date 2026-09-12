import { StyleSheet, View } from 'react-native';
import Animated, {
  Extrapolation,
  interpolate,
  useAnimatedStyle,
  type SharedValue,
} from 'react-native-reanimated';
import { Text, Wordmark } from '@/components/ui';

interface Props {
  scrollY: SharedValue<number>;
  /** Already formatted; the title never does arithmetic. */
  value: string | null;
}

/** Where the hero has scrolled far enough that the balance is off screen. */
const START = 44;
const END = 96;

/**
 * The navigation title, which hands over as the hero leaves.
 *
 * While the balance is on screen the bar carries the product; once it scrolls
 * away the bar carries the balance, so the number you came for is never more
 * than a glance away. The two crossfade rather than cut, and both are absolutely
 * positioned so neither reflows the bar as the other appears.
 *
 * Opacity only, driven on the UI thread — this runs on every scroll frame, so
 * it can afford nothing else. It is also why the transition needs no Reduce
 * Motion branch: a cross-fade is the reduced-motion form.
 */
export function StudioTitle({ scrollY, value }: Props) {
  const brand = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [START, END], [1, 0], Extrapolation.CLAMP),
  }));

  const balance = useAnimatedStyle(() => ({
    opacity: interpolate(scrollY.value, [START, END], [0, 1], Extrapolation.CLAMP),
  }));

  return (
    <View style={styles.title}>
      <Animated.View style={[styles.layer, brand]}>
        <Wordmark compact size={24} />
      </Animated.View>

      {value ? (
        <Animated.View style={[styles.layer, balance]}>
          <Text numeric variant="headline">
            {value}
          </Text>
        </Animated.View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  // A fixed box: the bar must not resize as the two layers swap.
  title: { height: 30, minWidth: 160, alignItems: 'center', justifyContent: 'center' },
  layer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
