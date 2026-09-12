import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Glyph, type GlyphName } from './Glyph';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

export type StatusTone = 'neutral' | 'active' | 'positive' | 'caution' | 'critical';

const palette: Record<StatusTone, { fg: string; bg: string; symbol: GlyphName }> = {
  neutral: { fg: tokens.color.text.secondary, bg: tokens.color.bg.sunken, symbol: 'circle' },
  active: { fg: tokens.color.accent.base, bg: tokens.color.accent.tint, symbol: 'clock' },
  positive: {
    fg: tokens.color.finance.gain,
    bg: tokens.color.finance.gainTint,
    symbol: 'checkmark.circle.fill',
  },
  caution: {
    fg: tokens.color.status.caution,
    bg: tokens.color.status.cautionTint,
    symbol: 'exclamationmark.triangle.fill',
  },
  critical: {
    fg: tokens.color.finance.loss,
    bg: tokens.color.finance.lossTint,
    symbol: 'xmark.circle.fill',
  },
};

interface Props {
  label: string;
  tone?: StatusTone;
  /** Overrides the tone's default glyph when a more specific one exists. */
  symbol?: GlyphName;
  style?: StyleProp<ViewStyle>;
}

/**
 * Status is always a glyph plus a word. Colour reinforces; it never carries
 * the meaning on its own.
 *
 * The label wraps rather than truncating — a long status such as
 * "reconciliation required" must never clip, so the badge grows instead.
 */
export function StatusBadge({ label, symbol, style, tone = 'neutral' }: Props) {
  const { bg, fg, symbol: defaultSymbol } = palette[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }, style]}>
      <Glyph color={fg} name={symbol ?? defaultSymbol} size={12} style={styles.symbol} />
      <Text style={[styles.label, { color: fg }]} variant="caption">
        {label}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: 'flex-start',
    minHeight: 26,
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.xs + tokens.optical.nudge,
    paddingHorizontal: tokens.space.sm + tokens.optical.hair,
    paddingVertical: tokens.space.xs + tokens.optical.hair,
    borderRadius: tokens.radius.sm,
    borderCurve: 'continuous',
    maxWidth: '100%',
  },
  // The SF Symbol's optical centre sits a hair below the cap height of the label.
  symbol: { marginTop: -tokens.optical.hair },
  label: { flexShrink: 1 },
});
