import { ActivityIndicator, StyleSheet } from 'react-native';
import { Glyph, type GlyphName } from '@/components/ui/Glyph';
import { Text } from '@/components/ui/Text';
import { Touchable } from '@/components/ui/Touchable';
import { tokens } from '@/theme/tokens';

interface Props {
  label: string;
  onPress(): void;
  symbol?: GlyphName;
  /** Shows the label next to the glyph instead of only announcing it. */
  showLabel?: boolean;
  loading?: boolean;
}

/**
 * A control in a native header. Rendered inside system chrome, so it carries no
 * material of its own — glass on glass reduces contrast.
 */
export function HeaderButton({
  label,
  loading = false,
  onPress,
  showLabel = false,
  symbol,
}: Props) {
  return (
    <Touchable
      accessibilityLabel={label}
      accessibilityRole="button"
      accessibilityState={{ busy: loading, disabled: loading }}
      disabled={loading}
      feedback="opacity"
      hitSlop={10}
      onPress={onPress}
      style={styles.button}
    >
      {loading ? (
        <ActivityIndicator color={tokens.color.accent.base} size="small" />
      ) : symbol ? (
        <Glyph color={tokens.color.accent.base} name={symbol} size={17} weight="semibold" />
      ) : null}
      {!loading && (showLabel || !symbol) ? (
        <Text tone="accent" variant="subhead">
          {label}
        </Text>
      ) : null}
    </Touchable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: tokens.layout.touch,
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.xs + 2,
    paddingHorizontal: tokens.space.xs,
  },
});
