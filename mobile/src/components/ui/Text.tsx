import { Text as RNText, StyleSheet, type TextProps } from 'react-native';
import { tokens, type TypeVariant } from '@/theme/tokens';

export type TextTone =
  | 'primary'
  | 'secondary'
  | 'tertiary'
  | 'inverse'
  | 'accent'
  | 'gain'
  | 'loss'
  | 'caution';

const tones: Record<TextTone, string> = {
  primary: tokens.color.text.primary,
  secondary: tokens.color.text.secondary,
  tertiary: tokens.color.text.tertiary,
  inverse: tokens.color.text.inverse,
  accent: tokens.color.accent.base,
  gain: tokens.color.finance.gain,
  loss: tokens.color.finance.loss,
  caution: tokens.color.status.caution,
};

export interface AppTextProps extends TextProps {
  variant?: TypeVariant;
  tone?: TextTone;
  /** Tabular figures. Use for anything that is a number. */
  numeric?: boolean;
  center?: boolean;
  /**
   * Shrinks to stay on one line instead of wrapping.
   *
   * Only for money in a constrained box. At accessibility text sizes a
   * currency amount would otherwise break at the decimal — "$5,103" above
   * ".64" — which is worse than a smaller, whole, readable figure. The floor
   * keeps it well above the 12pt minimum.
   */
  fit?: boolean;
}

/**
 * The only way text enters the app.
 *
 * Dynamic Type stays on; the multiplier ceiling comes from tokens so a single
 * change tunes every screen at once.
 */
export function Text({
  variant = 'body',
  tone = 'primary',
  numeric,
  center,
  fit,
  style,
  ...rest
}: AppTextProps) {
  return (
    <RNText
      maxFontSizeMultiplier={tokens.maxFontSizeMultiplier}
      {...(fit ? { numberOfLines: 1, adjustsFontSizeToFit: true, minimumFontScale: 0.6 } : null)}
      {...rest}
      style={[
        tokens.type[variant],
        { color: tones[tone] },
        numeric && tokens.tabular,
        center && styles.center,
        style,
      ]}
    />
  );
}

const styles = StyleSheet.create({ center: { textAlign: 'center' } });
