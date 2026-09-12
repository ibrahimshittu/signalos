import { SymbolView, type AndroidSymbol, type SFSymbol } from 'expo-symbols';
import { Platform, View, type StyleProp, type ViewStyle } from 'react-native';
import { tokens } from '@/theme/tokens';

export type GlyphName = SFSymbol;

interface Props {
  name: GlyphName;
  /** Material Symbols name used on Android and web. */
  android?: AndroidSymbol;
  size?: number;
  color?: string;
  weight?: 'regular' | 'medium' | 'semibold';
  /**
   * Provide this whenever the symbol carries meaning that isn't already in
   * adjacent text. Omit it for purely decorative glyphs.
   */
  label?: string;
  style?: StyleProp<ViewStyle>;
}

/**
 * SF Symbols on iOS, Material Symbols elsewhere.
 *
 * Icons never carry status on their own — a status always ships an adjacent
 * word, so a missing glyph degrades to something still readable.
 */
export function Glyph({
  name,
  android,
  size = 18,
  color = tokens.color.text.secondary,
  weight = 'medium',
  label,
  style,
}: Props) {
  const accessibility = label
    ? ({ accessible: true, accessibilityRole: 'image' as const, accessibilityLabel: label })
    : ({ accessible: false, importantForAccessibility: 'no-hide-descendants' as const });

  return (
    <SymbolView
      {...accessibility}
      name={android ? { ios: name, android, web: android } : name}
      size={size}
      tintColor={color}
      weight={weight}
      resizeMode="scaleAspectFit"
      fallback={<View style={{ width: size, height: size }} />}
      style={[{ width: size, height: size }, style]}
    />
  );
}

/** Directional glyph for a signed change, so direction survives greyscale. */
export function changeGlyph(value: number): GlyphName {
  if (value > 0) return 'arrow.up.right';
  if (value < 0) return 'arrow.down.right';
  return 'minus';
}

export const supportsSFSymbols = Platform.OS === 'ios';
