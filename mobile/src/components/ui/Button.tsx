import { ActivityIndicator, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Glyph, type GlyphName } from './Glyph';
import { Text } from './Text';
import { Touchable } from './Touchable';
import { tokens } from '@/theme/tokens';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'destructive';

interface Props {
  title: string;
  onPress(): void;
  variant?: ButtonVariant;
  size?: 'regular' | 'compact';
  icon?: GlyphName;
  loading?: boolean;
  disabled?: boolean;
  /** Reads as the full sentence to VoiceOver when the title alone is terse. */
  accessibilityHint?: string;
  style?: StyleProp<ViewStyle>;
}

/**
 * Filled, tinted, plain — the same three weights UIKit uses.
 *
 * Outlined buttons were the previous approach and read as floating chips on a
 * light canvas: the border drew more attention than the label, and a red
 * outline made a secondary destructive action shout louder than the primary.
 * A tint carries the same meaning while staying quieter than a fill.
 */
const fills: Record<ButtonVariant, ViewStyle> = {
  primary: { backgroundColor: tokens.color.accent.base },
  secondary: { backgroundColor: tokens.color.bg.sunken },
  tertiary: { backgroundColor: 'transparent' },
  destructive: { backgroundColor: tokens.color.finance.lossTint },
};

const labelTones = {
  primary: 'inverse',
  secondary: 'primary',
  tertiary: 'accent',
  destructive: 'loss',
} as const;

/**
 * Rectangular with a restrained radius — never a capsule.
 *
 * The radius is paired to the height (14 at 50pt, 12 at 44pt) so the curve
 * stays proportionate across sizes. Loading keeps the button's full height, so
 * the layout never jumps underneath a decision the user is midway through.
 */
export function Button({
  title,
  onPress,
  variant = 'primary',
  size = 'regular',
  icon,
  loading = false,
  disabled = false,
  accessibilityHint,
  style,
}: Props) {
  const blocked = loading || disabled;
  const regular = size === 'regular';
  const foreground =
    variant === 'primary'
      ? tokens.color.text.inverse
      : variant === 'destructive'
        ? tokens.color.finance.loss
        : variant === 'tertiary'
          ? tokens.color.accent.base
          : tokens.color.text.primary;

  return (
    <Touchable
      accessibilityHint={accessibilityHint}
      accessibilityLabel={title}
      accessibilityRole="button"
      accessibilityState={{ disabled: blocked, busy: loading }}
      disabled={blocked}
      onPress={onPress}
      style={[
        styles.base,
        regular ? styles.regular : styles.compact,
        fills[variant],
        disabled && !loading && styles.blocked,
        style,
      ]}
    >
      <View style={styles.content}>
        <View pointerEvents="none" style={styles.indicator}>
          {loading ? (
            <ActivityIndicator color={foreground} />
          ) : icon ? (
            <Glyph color={foreground} name={icon} size={16} />
          ) : null}
        </View>
        <Text
          center
          style={styles.label}
          tone={labelTones[variant]}
          variant={regular ? 'headline' : 'subhead'}
        >
          {title}
        </Text>
      </View>
    </Touchable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderCurve: 'continuous',
    alignItems: 'center',
    justifyContent: 'center',
  },
  regular: {
    minHeight: tokens.layout.control,
    borderRadius: tokens.radius.lg,
    paddingHorizontal: tokens.space.lg,
    paddingVertical: tokens.space.md,
  },
  compact: {
    minHeight: tokens.layout.controlCompact,
    borderRadius: tokens.radius.md,
    paddingHorizontal: tokens.space.base,
    paddingVertical: tokens.space.sm,
  },
  blocked: { opacity: 0.45 },
  content: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: tokens.space.xl,
    maxWidth: '100%',
  },
  label: { flexShrink: 1 },
  indicator: {
    position: 'absolute',
    left: 0,
    width: tokens.space.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
