import { StyleSheet, View } from 'react-native';
import Animated, { FadeIn, useReducedMotion } from 'react-native-reanimated';
import { Glyph } from './Glyph';
import { Text } from './Text';
import { Touchable } from './Touchable';
import * as haptics from '@/lib/haptics';
import { tokens } from '@/theme/tokens';

interface Props {
  title: string;
  detail?: string;
  selected: boolean;
  onPress(): void;
  /** Multi-select renders a square control and reports the checkbox role. */
  multiple?: boolean;
}

/**
 * A single answer in a question list.
 *
 * Selection changes three things at once — the control fills, the title gains
 * weight, and the card takes a tint — so the state reads at a glance, survives
 * greyscale, and never depends on colour alone.
 *
 * The border stays 1pt in both states; thickening it on selection would shift
 * the text inside by half a point and make the list twitch.
 */
export function OptionRow({ detail, multiple = false, onPress, selected, title }: Props) {
  const reduceMotion = useReducedMotion();
  return (
    <Touchable
      accessibilityRole={multiple ? 'checkbox' : 'radio'}
      accessibilityState={multiple ? { checked: selected } : { selected }}
      feedback="highlight"
      onPress={() => {
        haptics.selection();
        onPress();
      }}
      style={[styles.card, selected && styles.cardSelected]}
    >
      <View style={styles.copy}>
        <Text variant="headline">{title}</Text>
        {detail ? (
          <Text style={styles.detail} tone="secondary" variant="footnote">
            {detail}
          </Text>
        ) : null}
      </View>

      <View
        style={[
          styles.control,
          multiple && styles.controlSquare,
          selected && styles.controlSelected,
        ]}
      >
        {selected ? (
          <Animated.View
            entering={reduceMotion ? undefined : FadeIn.duration(tokens.motion.duration.state)}
          >
            <Glyph color={tokens.color.text.inverse} name="checkmark" size={12} weight="semibold" />
          </Animated.View>
        ) : null}
      </View>
    </Touchable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: 60,
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.base,
    paddingVertical: tokens.space.base - tokens.optical.nudge,
    paddingHorizontal: tokens.space.base,
    borderRadius: tokens.radius.md,
    borderCurve: 'continuous',
    borderWidth: 1,
    borderColor: tokens.color.border.hairline,
    backgroundColor: tokens.color.bg.surface,
  },
  cardSelected: {
    borderColor: tokens.color.accent.base,
    backgroundColor: tokens.color.accent.tint,
  },
  copy: { flex: 1 },
  detail: { marginTop: tokens.space.xs },
  control: {
    width: 22,
    height: 22,
    borderRadius: tokens.radius.full,
    borderWidth: 1.5,
    borderColor: tokens.color.border.strong,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // A checkbox reads as square; the radius is scaled to the 22pt control.
  controlSquare: { borderRadius: 7 },
  controlSelected: {
    backgroundColor: tokens.color.accent.base,
    borderColor: tokens.color.accent.base,
  },
});
