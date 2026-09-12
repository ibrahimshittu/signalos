import { Platform, StyleSheet, View } from 'react-native';
import Svg, { Path, Rect } from 'react-native-svg';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

/**
 * The SignalOS mark.
 *
 * A signal read cleanly: three points rising through a bounded frame. It is
 * drawn as a filled tile rather than a bare stroke so it holds its weight at
 * 20pt in a navigation bar and still works as an app icon, where a thin line
 * would disappear. The path is geometric — every vertex lands on the grid —
 * which is what keeps it from reading as a hand-drawn squiggle.
 */
export function BrandMark({
  size = 28,
  tint = tokens.color.accent.base,
  onTint = tokens.color.text.inverse,
  decorative = false,
}: {
  size?: number;
  tint?: string;
  onTint?: string;
  decorative?: boolean;
}) {
  return (
    <Svg
      accessibilityLabel={decorative ? undefined : 'SignalOS'}
      accessibilityRole={decorative ? undefined : 'image'}
      accessible={Platform.OS === 'web' ? undefined : !decorative}
      aria-hidden={decorative || undefined}
      height={size}
      viewBox="0 0 32 32"
      width={size}
    >
      <Rect fill={tint} height={32} rx={9} ry={9} width={32} x={0} y={0} />
      <Path
        d="M7.5 21.5 13 15.5 17 19 24.5 10.5"
        fill="none"
        stroke={onTint}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2.75}
      />
    </Svg>
  );
}

interface WordmarkProps {
  size?: number;
  /** Header lockups sit tighter than a hero lockup. */
  compact?: boolean;
}

export function Wordmark({ compact = false, size = 28 }: WordmarkProps) {
  return (
    <View accessible accessibilityLabel="SignalOS" accessibilityRole="image" style={styles.lockup}>
      <BrandMark decorative size={size} />
      <Text variant={compact ? 'headline' : 'title3'}>SignalOS</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  lockup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.sm + tokens.optical.nudge,
  },
});
