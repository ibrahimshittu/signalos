import { type ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Glyph } from './Glyph';
import { Text } from './Text';
import { Touchable } from './Touchable';
import { tokens } from '@/theme/tokens';

/**
 * A grouped block of related rows.
 *
 * Used where content is a set of facts about one thing — an account, a
 * connection, a mandate. Editorial screens stay flat; this is what keeps the
 * two reading differently instead of every screen becoming the same grid.
 */
export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

interface RowProps {
  label: string;
  /** Identity that belongs to the row itself, such as a provider mark. */
  leading?: ReactNode;
  /** Promotes the label to the row's subject rather than its field name. */
  emphasis?: boolean;
  /** Right-aligned. Omit for a row whose content is entirely in `children`. */
  value?: string;
  /** Second line under the label, for the reason behind a number. */
  detail?: string;
  numeric?: boolean;
  tone?: 'primary' | 'loss' | 'gain' | 'caution';
  trailing?: ReactNode;
  onPress?: () => void;
  accessibilityHint?: string;
  last?: boolean;
  children?: ReactNode;
}

const HORIZONTAL = tokens.space.base;

export function CardRow({
  accessibilityHint,
  children,
  detail,
  emphasis = false,
  label,
  last = false,
  leading,
  numeric = true,
  onPress,
  tone = 'primary',
  trailing,
  value,
}: RowProps) {
  const content = (
    <>
      {leading}
      <View style={styles.labelColumn}>
        <Text tone={emphasis ? 'primary' : 'secondary'} variant={emphasis ? 'headline' : 'callout'}>
          {label}
        </Text>
        {detail ? (
          <Text style={styles.detail} tone="tertiary" variant="footnote">
            {detail}
          </Text>
        ) : null}
      </View>

      {children ?? (
        <View style={[styles.valueColumn, !value && !trailing && styles.disclosureColumn]}>
          {value ? (
            <Text numeric={numeric} style={styles.value} tone={tone} variant="subhead">
              {value}
            </Text>
          ) : null}
          {trailing}
          {onPress ? (
            <Glyph color={tokens.color.text.tertiary} name="chevron.right" size={13} />
          ) : null}
        </View>
      )}

      {last ? null : <View style={styles.separator} />}
    </>
  );

  if (!onPress) return <View style={styles.row}>{content}</View>;

  return (
    <Touchable
      accessibilityHint={accessibilityHint}
      accessibilityRole="button"
      feedback="highlight"
      highlightRadius={0}
      onPress={onPress}
      style={styles.row}
    >
      {content}
    </Touchable>
  );
}

const styles = StyleSheet.create({
  card: {
    ...tokens.elevation.surface,
    overflow: 'hidden',
  },
  row: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.space.md,
    paddingHorizontal: HORIZONTAL,
    paddingVertical: tokens.space.md,
  },
  labelColumn: { flex: 1.1, justifyContent: 'center' },
  valueColumn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: tokens.space.sm,
  },
  detail: { marginTop: tokens.optical.nudge },
  disclosureColumn: { flex: 0 },
  value: { textAlign: 'right', flexShrink: 1 },
  /**
   * Inset from the label edge rather than the card edge, so the eye reads the
   * rows as one list instead of a stack of separate bands.
   */
  separator: {
    position: 'absolute',
    left: HORIZONTAL,
    right: 0,
    bottom: 0,
    height: StyleSheet.hairlineWidth,
    backgroundColor: tokens.color.border.separator,
  },
});
