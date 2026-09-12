import { StyleSheet, View, type DimensionValue } from 'react-native';
import Animated, { FadeIn, useReducedMotion } from 'react-native-reanimated';
import { Button, type ButtonVariant } from './Button';
import { Glyph, type GlyphName } from './Glyph';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

/** A single placeholder bar. Static — a shimmer would animate on every refresh. */
export function Skeleton({
  width = '100%',
  height = 16,
}: {
  width?: DimensionValue;
  height?: number;
}) {
  return <View accessibilityElementsHidden style={[styles.skeleton, { width, height }]} />;
}

/** Placeholder that matches the shape of the block it replaces. */
export function LoadingBlock({ lines = 3 }: { lines?: number }) {
  return (
    <View accessibilityLabel="Loading" accessible style={styles.loading}>
      <Skeleton height={12} width="34%" />
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton height={index === 0 ? 34 : 16} key={index} width={index === 0 ? '58%' : '100%'} />
      ))}
    </View>
  );
}

interface EmptyProps {
  title: string;
  body: string;
  symbol?: GlyphName;
  action?: {
    title: string;
    onPress(): void;
    icon?: GlyphName;
    loading?: boolean;
    variant?: ButtonVariant;
  };
  /**
   * `center` when the state owns a whole screen, `leading` when it sits inside
   * a section whose heading is already left-aligned above it.
   */
  align?: 'leading' | 'center';
  /** Reduces vertical air when the state sits between two populated sections. */
  density?: 'regular' | 'compact';
}

/**
 * Empty is not failure. In SignalOS a quiet screen usually means the system
 * declined to force a trade, so the copy says that rather than apologising.
 */
export function EmptyState({
  action,
  align = 'leading',
  body,
  density = 'regular',
  symbol,
  title,
}: EmptyProps) {
  const reduceMotion = useReducedMotion();
  const centred = align === 'center';

  return (
    <Animated.View
      entering={reduceMotion ? undefined : FadeIn.duration(tokens.motion.duration.enter)}
      style={[styles.state, centred && styles.centred, density === 'compact' && styles.compact]}
    >
      {symbol ? <Glyph color={tokens.color.text.secondary} name={symbol} size={24} /> : null}
      <Text
        center={centred}
        style={symbol ? styles.stateTitleAfterSymbol : undefined}
        variant="title3"
      >
        {title}
      </Text>
      <Text
        center={centred}
        style={[styles.stateBody, centred && styles.centredBody]}
        tone="secondary"
        variant="callout"
      >
        {body}
      </Text>
      {action ? (
        <Button
          icon={action.icon}
          loading={action.loading}
          onPress={action.onPress}
          size="compact"
          style={styles.stateAction}
          title={action.title}
          variant={action.variant ?? 'secondary'}
        />
      ) : null}
    </Animated.View>
  );
}

interface ErrorProps {
  title?: string;
  body?: string;
  onRetry(): void;
  retrying?: boolean;
}

/** A failed load. Never implies the user's money is at risk. */
export function ErrorState({
  body = 'Nothing was submitted and nothing changed. Try again when you are ready.',
  onRetry,
  retrying = false,
  title = 'That did not load',
}: ErrorProps) {
  return (
    <View accessibilityLiveRegion="polite" accessibilityRole="alert" style={styles.state}>
      <Glyph color={tokens.color.status.caution} name="exclamationmark.triangle" size={26} />
      <Text style={styles.stateTitle} variant="title3">
        {title}
      </Text>
      <Text style={styles.stateBody} tone="secondary" variant="callout">
        {body}
      </Text>
      <Button
        loading={retrying}
        onPress={onRetry}
        size="compact"
        style={styles.stateAction}
        title="Try again"
        variant="secondary"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  skeleton: {
    backgroundColor: tokens.color.bg.sunken,
    borderRadius: tokens.radius.sm,
    borderCurve: 'continuous',
  },
  loading: { gap: tokens.space.md, paddingVertical: tokens.space.base },
  state: { paddingVertical: tokens.space.xxl, alignItems: 'flex-start' },
  centred: { alignItems: 'center', paddingVertical: tokens.space.xxxl },
  compact: { paddingVertical: tokens.space.xxl },
  stateTitle: { marginTop: tokens.space.base },
  stateTitleAfterSymbol: { marginTop: tokens.space.base },
  stateBody: { marginTop: tokens.space.sm, maxWidth: 360 },
  centredBody: { maxWidth: 300 },
  stateAction: { marginTop: tokens.space.lg },
});
