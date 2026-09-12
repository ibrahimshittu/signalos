import { type PropsWithChildren, useEffect, useState } from 'react';
import { AccessibilityInfo, Platform, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { BlurView } from 'expo-blur';
import { GlassView, isGlassEffectAPIAvailable, isLiquidGlassAvailable } from 'expo-glass-effect';
import { tokens } from '@/theme/tokens';

const supportsLiquidGlass =
  Platform.OS === 'ios' && isGlassEffectAPIAvailable() && isLiquidGlassAvailable();

/** Tracks the Reduce Transparency setting, including changes while running. */
export function useReduceTransparency(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    if (Platform.OS !== 'ios') return;
    let active = true;
    AccessibilityInfo.isReduceTransparencyEnabled().then((value) => {
      if (active) setReduced(value);
    });
    const subscription = AccessibilityInfo.addEventListener('reduceTransparencyChanged', setReduced);
    return () => {
      active = false;
      subscription.remove();
    };
  }, []);
  return reduced;
}

type Props = PropsWithChildren<{
  /** `true` for glass the user presses, so it responds to touch like system chrome. */
  interactive?: boolean;
  /**
   * Applied to the effect layer itself, not just the wrapper. The native glass
   * view renders its own material, so a parent `overflow: hidden` does not
   * round it — the corner has to be on the layer that draws.
   */
  radius?: number;
  style?: StyleProp<ViewStyle>;
}>;

/**
 * Liquid Glass, restricted to the functional layer.
 *
 * Per Apple's guidance, glass floats above content to give structure without
 * stealing focus — so this is only ever used for navigation chrome, toolbars,
 * modal headers, and the floating approval tray. It is never applied to
 * portfolio values, data rows, forms, or signal content.
 *
 * Degrades: Liquid Glass (iOS 26+) → system material blur → opaque surface when
 * Reduce Transparency is on.
 */
export function Glass({ children, interactive = false, radius = tokens.radius.xl, style }: Props) {
  const reduceTransparency = useReduceTransparency();

  if (reduceTransparency) {
    return <View style={[styles.base, styles.opaque, { borderRadius: radius }, style]}>{children}</View>;
  }

  if (supportsLiquidGlass) {
    return (
      <GlassView
        glassEffectStyle="regular"
        isInteractive={interactive}
        style={[styles.base, { borderRadius: radius }, style]}>
        {children}
      </GlassView>
    );
  }

  return (
    <BlurView intensity={80} style={[styles.base, { borderRadius: radius }, style]} tint="systemMaterial">
      {children}
    </BlurView>
  );
}

const styles = StyleSheet.create({
  base: { overflow: 'hidden', borderCurve: 'continuous' },
  opaque: {
    backgroundColor: tokens.color.materialFallback,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: tokens.color.border.hairline,
  },
});
