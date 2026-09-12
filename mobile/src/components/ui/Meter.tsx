import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { tokens } from '@/theme/tokens';

interface Props {
  /** 0 to 1. Values outside the range are clamped rather than overflowing. */
  value: number;
  width?: number;
  tint?: string;
  style?: StyleProp<ViewStyle>;
}

/**
 * A bounded quantity at a glance, alongside the number it summarises.
 *
 * It is never the only representation of a value — the figure is always
 * present too, so the meter can stay small enough to sit inside a table row.
 */
export function Meter({ style, tint = tokens.color.accent.base, value, width = 44 }: Props) {
  const filled = Math.max(0, Math.min(1, value));
  return (
    <View accessibilityElementsHidden style={[styles.track, { width }, style]}>
      <View style={[styles.fill, { backgroundColor: tint, width: `${filled * 100}%` }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    height: 4,
    borderRadius: tokens.radius.full,
    backgroundColor: tokens.color.bg.sunken,
    overflow: 'hidden',
  },
  fill: { height: 4, borderRadius: tokens.radius.full },
});
