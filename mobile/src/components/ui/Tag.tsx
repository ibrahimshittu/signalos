import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

interface Props {
  label: string;
  /** `accent` marks the live environment; `neutral` everything else. */
  tone?: 'neutral' | 'accent';
  style?: StyleProp<ViewStyle>;
}

/**
 * A classification, not a state.
 *
 * `StatusBadge` says how something is doing and always carries a glyph. A tag
 * says what something *is* — "Mainnet", "Perpetual" — so it needs no glyph and
 * stays visually quieter, which keeps a row with both from reading as two
 * competing alerts.
 */
export function Tag({ label, style, tone = 'neutral' }: Props) {
  const accent = tone === 'accent';
  return (
    <View style={[styles.tag, accent ? styles.accent : styles.neutral, style]}>
      <Text tone={accent ? 'accent' : 'secondary'} variant="caption">
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    alignSelf: 'flex-start',
    minHeight: 22,
    justifyContent: 'center',
    paddingHorizontal: tokens.space.sm,
    paddingVertical: tokens.optical.tick,
    borderRadius: tokens.radius.sm - tokens.optical.nudge,
    borderCurve: 'continuous',
    borderWidth: StyleSheet.hairlineWidth,
  },
  neutral: {
    backgroundColor: tokens.color.bg.sunken,
    borderColor: tokens.color.border.hairline,
  },
  accent: {
    backgroundColor: tokens.color.accent.tint,
    borderColor: 'transparent',
  },
});
