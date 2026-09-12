import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Glyph, changeGlyph } from './Glyph';
import { Text } from './Text';
import { colorForChange, tokens } from '@/theme/tokens';

interface MetricProps {
  label: string;
  value: string;
  detail?: string;
  size?: 'hero' | 'regular';
  /** Spoken instead of the raw glyph string, so VoiceOver reads money properly. */
  accessibilityLabel?: string;
  style?: StyleProp<ViewStyle>;
}

/**
 * A labelled figure.
 *
 * The label sits above the value so a row of metrics aligns on its numbers,
 * which is what the eye compares — not on labels of differing length.
 */
export function Metric({ accessibilityLabel, detail, label, size = 'regular', style, value }: MetricProps) {
  const hero = size === 'hero';
  return (
    <View style={style}>
      <Text tone={hero ? 'secondary' : 'tertiary'} variant={hero ? 'subhead' : 'caption'}>
        {label}
      </Text>
      <Text
        accessibilityLabel={accessibilityLabel ?? `${label} ${value}`}
        fit={hero}
        numeric
        style={hero ? styles.heroValue : styles.value}
        variant={hero ? 'hero' : 'title3'}>
        {value}
      </Text>
      {detail ? (
        <Text style={styles.detail} tone="tertiary" variant="footnote">
          {detail}
        </Text>
      ) : null}
    </View>
  );
}

interface ChangeProps {
  /** Signed change. Sign and arrow carry the direction; colour only reinforces. */
  value: number;
  formatted: string;
  period: string;
  variant?: 'headline' | 'subhead' | 'footnote';
}

/** A signed performance change. Never relies on colour alone. */
export function Change({ formatted, period, value, variant = 'subhead' }: ChangeProps) {
  const tint = colorForChange(value);
  const direction = value > 0 ? 'up' : value < 0 ? 'down' : 'unchanged';
  return (
    <View accessibilityLabel={`${formatted} ${direction} ${period}`} accessible style={styles.change}>
      <Glyph color={tint} name={changeGlyph(value)} size={13} />
      <Text numeric style={{ color: tint }} variant={variant}>
        {formatted}
      </Text>
      <Text tone="tertiary" variant={variant === 'footnote' ? 'footnote' : 'subhead'}>
        {period}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  // Large type already carries its own optical space above the cap height.
  heroValue: { marginTop: tokens.space.xs + tokens.optical.nudge },
  value: { marginTop: tokens.optical.tick },
  detail: { marginTop: tokens.space.xs },
  change: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.xs + tokens.optical.nudge,
    flexWrap: 'wrap',
  },
});
