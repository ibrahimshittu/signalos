import { type ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

interface SectionProps {
  title: string;
  /**
   * A pending count, shown as a chip beside the title.
   *
   * This is the one place emphasis is earned rather than manufactured: it is a
   * factual number of items waiting on the user, like an inbox, so it draws the
   * eye without a colour escalation, a countdown, or an exclamation.
   */
  count?: number;
  /** One line of context. Factual — this is not a tagline slot. */
  caption?: string;
  /** Right-aligned control, typically a link to the full list. */
  action?: ReactNode;
  children?: ReactNode;
  /**
   * `primary` for the section a screen exists for: more air, larger title, no
   * rule. `secondary` for supporting material: a rule and a smaller title.
   * Uniform section headers are what make a screen read as a form.
   */
  level?: 'primary' | 'secondary';
  style?: StyleProp<ViewStyle>;
}

export function Section({
  action,
  caption,
  children,
  count,
  level = 'secondary',
  style,
  title,
}: SectionProps) {
  const primary = level === 'primary';
  return (
    <View style={[primary ? styles.primary : styles.secondary, style]}>
      <View style={styles.header}>
        <View style={styles.heading}>
          <View style={styles.titleRow}>
            <Text accessibilityRole="header" variant={primary ? 'title2' : 'title3'}>
              {title}
            </Text>
            {count ? (
              <View style={styles.count}>
                <Text numeric tone="inverse" variant="caption">
                  {count}
                </Text>
              </View>
            ) : null}
          </View>
        </View>
        {action}
      </View>
      {caption ? (
        <Text style={styles.caption} tone="secondary" variant="footnote">
          {caption}
        </Text>
      ) : null}
      {children}
    </View>
  );
}

/** A hairline rule. `inset` aligns it with text rather than the screen edge. */
export function Divider({
  inset = false,
  style,
}: {
  inset?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  return <View style={[styles.divider, inset && styles.dividerInset, style]} />;
}

const styles = StyleSheet.create({
  primary: { marginTop: tokens.space.xxl },
  secondary: {
    marginTop: tokens.space.xxl,
    paddingTop: tokens.space.lg,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: tokens.color.border.hairline,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: tokens.space.base,
  },
  heading: { flex: 1 },
  titleRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: tokens.space.sm },
  count: {
    minWidth: 24,
    height: 24,
    paddingHorizontal: tokens.space.xs + tokens.optical.nudge,
    borderRadius: tokens.radius.full,
    backgroundColor: tokens.color.accent.base,
    alignItems: 'center',
    justifyContent: 'center',
  },
  caption: { marginTop: tokens.space.xs + tokens.optical.nudge },
  divider: { height: StyleSheet.hairlineWidth, backgroundColor: tokens.color.border.hairline },
  dividerInset: { marginLeft: tokens.space.xxxl },
});
