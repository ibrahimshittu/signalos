import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Glyph, type GlyphName } from './Glyph';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

export type CalloutTone = 'info' | 'caution' | 'positive';

const palette: Record<CalloutTone, { fg: string; bg: string; symbol: GlyphName }> = {
  info: { fg: tokens.color.status.info, bg: tokens.color.status.infoTint, symbol: 'info.circle.fill' },
  caution: {
    fg: tokens.color.status.caution,
    bg: tokens.color.status.cautionTint,
    symbol: 'exclamationmark.triangle.fill',
  },
  positive: {
    fg: tokens.color.finance.gain,
    bg: tokens.color.finance.gainTint,
    symbol: 'checkmark.circle.fill',
  },
};

interface Props {
  title: string;
  body: string;
  tone?: CalloutTone;
  /** Announce immediately — use for state that changed as a result of an action. */
  live?: boolean;
  style?: StyleProp<ViewStyle>;
}

/**
 * A boundary or a consequence, stated inline.
 *
 * Used sparingly and never for marketing. The tint carries the tone and the
 * glyph repeats it, so the meaning survives greyscale; the body stays
 * secondary so the callout never outweighs the content it qualifies.
 */
export function Callout({ body, live = false, style, title, tone = 'info' }: Props) {
  const { bg, fg, symbol } = palette[tone];
  return (
    <View
      accessibilityLiveRegion={live ? 'polite' : 'none'}
      accessibilityRole={live ? 'alert' : undefined}
      style={[styles.callout, { backgroundColor: bg }, style]}>
      <Glyph color={fg} name={symbol} size={16} style={styles.symbol} />
      <View style={styles.copy}>
        <Text style={{ color: fg }} variant="subhead">
          {title}
        </Text>
        <Text style={styles.body} tone="secondary" variant="footnote">
          {body}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  callout: {
    flexDirection: 'row',
    gap: tokens.space.md,
    padding: tokens.space.base,
    borderRadius: tokens.radius.md,
    borderCurve: 'continuous',
  },
  // Aligns the glyph to the cap height of the title rather than its line box.
  symbol: { marginTop: tokens.optical.nudge },
  copy: { flex: 1 },
  body: { marginTop: tokens.space.xs },
});
