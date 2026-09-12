import { StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Button, Glass, Glyph, Text } from '@/components/ui';
import type { Expiry } from '@/domain/proposal';
import { formatUsd } from '@/lib/format';
import { tokens } from '@/theme/tokens';

interface Props {
  maxLoss: number;
  expiry: Expiry;
  /** Label changes between opening secure approval and confirming the plan. */
  primaryTitle: string;
  onPrimary(): void;
  primaryDisabled?: boolean;
  primaryLoading?: boolean;
  onPass(): void;
  passLoading?: boolean;
  /** Closes the brief once the terms have lapsed and there is nothing to decide. */
  onDismiss(): void;
}

/**
 * The decision layer, floating over the brief.
 *
 * This is one of the few places Liquid Glass belongs: functional chrome above
 * content, reachable no matter how far the user has read. The worst case leads
 * at reading size and the expiry sits on its baseline, so approval can never
 * happen without the loss in view.
 *
 * Once the terms lapse the actions are replaced rather than disabled. A greyed
 * primary still looks like the thing to press, and pressing it does nothing —
 * a dead end at exactly the moment the user needs to know what changed.
 */
export function ApprovalTray({
  expiry,
  maxLoss,
  onDismiss,
  onPass,
  onPrimary,
  passLoading = false,
  primaryDisabled = false,
  primaryLoading = false,
  primaryTitle,
}: Props) {
  const insets = useSafeAreaInsets();
  const expired = expiry.state === 'expired';
  const urgent = expiry.state !== 'open';
  const tint = urgent ? tokens.color.status.caution : tokens.color.text.tertiary;

  return (
    <View
      pointerEvents="box-none"
      // Lifted clear of the bottom edge: a tray flush to the screen reads as
      // docked chrome, and this one is a decision surface hovering over a brief.
      style={[styles.layer, { bottom: Math.max(insets.bottom, tokens.space.md) }]}
    >
      <Glass interactive radius={tokens.radius.sheet} style={styles.tray}>
        <View style={styles.summary}>
          <View style={styles.loss}>
            <Text tone="secondary" variant="caption">
              Estimated loss at stop
            </Text>
            <Text fit numeric style={styles.lossValue} variant="title2">
              {formatUsd(maxLoss, { cents: true })}
            </Text>
          </View>
          <View style={styles.expiry}>
            <Glyph color={tint} name={expired ? 'clock.badge.xmark' : 'clock'} size={13} />
            <Text numeric style={{ color: tint }} variant="caption">
              {expiry.label}
            </Text>
          </View>
        </View>

        {expired ? (
          <View style={styles.expiredActions}>
            <Text style={styles.expiredNote} tone="secondary" variant="footnote">
              These proposal terms have expired. A new review is needed before an order can be
              submitted.
            </Text>
            <Button onPress={onDismiss} title="Close" variant="secondary" />
          </View>
        ) : (
          <View style={styles.actions}>
            <Button
              accessibilityHint="Authentication and order review come before an explicit order submission"
              disabled={primaryDisabled}
              loading={primaryLoading}
              onPress={onPrimary}
              style={styles.primary}
              title={primaryTitle}
            />
            <Button
              accessibilityHint="Declines this proposal and records why it was not a fit"
              loading={passLoading}
              disabled={primaryLoading}
              onPress={onPass}
              style={styles.pass}
              title="Pass"
              variant="secondary"
            />
          </View>
        )}
      </Glass>
    </View>
  );
}

const styles = StyleSheet.create({
  layer: {
    position: 'absolute',
    left: tokens.space.md,
    right: tokens.space.md,
    ...tokens.elevation.floating,
  },
  tray: {
    borderRadius: tokens.radius.sheet,
    // Buttons at `lg` sit exactly one padding step inside the tray's corner,
    // so the inner and outer curves stay concentric.
    padding: tokens.space.base,
    gap: tokens.space.base,
  },
  summary: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    gap: tokens.space.md,
  },
  loss: { flexShrink: 1 },
  lossValue: { marginTop: tokens.optical.tick },
  // Sits on the value's baseline rather than floating at the top of the row.
  expiry: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.xs,
    flexShrink: 1,
    paddingBottom: 2,
  },
  actions: { flexDirection: 'row', gap: tokens.space.sm },
  primary: { flex: 1 },
  // Wide enough for "Pass" plus its touch target, narrow enough that the
  // primary action stays visibly the larger of the two.
  pass: { flexBasis: 100 },
  expiredActions: { gap: tokens.space.md },
  expiredNote: { paddingHorizontal: tokens.optical.nudge },
});
