import { StyleSheet, View } from 'react-native';
import { Text } from './Text';
import { Touchable } from './Touchable';
import { tokens } from '@/theme/tokens';

interface Props {
  firstName: string;
  lastName: string;
  /** Omit to render the same mark as a static identity, not a control. */
  onPress?: () => void;
  size?: number;
}

function initials(firstName: string, lastName: string): string {
  const letters = `${firstName.charAt(0)}${lastName.charAt(0)}`.trim();
  return letters ? letters.toUpperCase() : 'SO';
}

/**
 * The account control in a navigation bar.
 *
 * Initials rather than a glyph: it is the one place the interface acknowledges
 * whose money this is, and it gives the header a fixed, recognisable anchor on
 * the right that never changes shape as connection state changes.
 */
export function Avatar({ firstName, lastName, onPress, size = 32 }: Props) {
  const shape = [styles.avatar, { width: size, height: size, borderRadius: size / 2 }];
  const label = (
    <Text style={styles.initials} variant={size >= 48 ? 'title3' : 'caption'}>
      {initials(firstName, lastName)}
    </Text>
  );

  if (!onPress) {
    return (
      <View accessibilityLabel={`${firstName} ${lastName}`.trim()} accessible style={shape}>
        {label}
      </View>
    );
  }

  return (
    <Touchable
      accessibilityHint="Opens your account, connection, and mandate"
      accessibilityLabel="Account"
      accessibilityRole="button"
      feedback="scale"
      hitSlop={8}
      onPress={onPress}
      style={shape}>
      {label}
    </Touchable>
  );
}

const styles = StyleSheet.create({
  avatar: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: tokens.color.bg.sunken,
  },
  initials: { fontWeight: '600' },
});
