import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  FadeIn,
  FadeInDown,
  FadeOut,
  FadeOutUp,
  useReducedMotion,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Glyph, type GlyphName } from './Glyph';
import { Text } from './Text';
import { Touchable } from './Touchable';
import { tokens } from '@/theme/tokens';

export type ToastTone = 'info' | 'success' | 'error';

export interface ToastInput {
  title: string;
  message?: string;
  tone?: ToastTone;
  /** Defaults to four seconds. Use zero for a persistent announcement. */
  durationMs?: number;
}

interface ToastMessage extends ToastInput {
  id: number;
}

interface ToastContextValue {
  showToast(input: ToastInput): void;
  dismissToast(): void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const palette: Record<ToastTone, { color: string; tint: string; symbol: GlyphName }> = {
  info: {
    color: tokens.color.status.info,
    tint: tokens.color.status.infoTint,
    symbol: 'info.circle.fill',
  },
  success: {
    color: tokens.color.finance.gain,
    tint: tokens.color.finance.gainTint,
    symbol: 'checkmark.circle.fill',
  },
  error: {
    color: tokens.color.status.caution,
    tint: tokens.color.status.cautionTint,
    symbol: 'exclamationmark.triangle.fill',
  },
};

/**
 * App-wide transient feedback.
 *
 * Toasts acknowledge state changes; they never carry the only explanation or
 * recovery control for an error. A single message is shown at a time so rapid
 * network events do not stack over the interface.
 */
export function ToastProvider({ children }: PropsWithChildren) {
  const insets = useSafeAreaInsets();
  const reduceMotion = useReducedMotion();
  const nextId = useRef(0);
  const [toast, setToast] = useState<ToastMessage | null>(null);

  const dismissToast = useCallback(() => setToast(null), []);
  const showToast = useCallback((input: ToastInput) => {
    nextId.current += 1;
    setToast({ ...input, id: nextId.current });
  }, []);

  useEffect(() => {
    if (!toast || toast.durationMs === 0) return;
    const timeout = setTimeout(dismissToast, toast.durationMs ?? 4_000);
    return () => clearTimeout(timeout);
  }, [dismissToast, toast]);

  const value = useMemo(() => ({ dismissToast, showToast }), [dismissToast, showToast]);
  const tone = toast?.tone ?? 'info';
  const appearance = palette[tone];

  return (
    <ToastContext.Provider value={value}>
      {children}
      <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
        {toast ? (
          <Animated.View
            accessibilityLiveRegion="polite"
            accessibilityRole={tone === 'error' ? 'alert' : undefined}
            entering={
              reduceMotion
                ? FadeIn.duration(tokens.motion.duration.state)
                : FadeInDown.duration(tokens.motion.duration.enter)
            }
            exiting={
              reduceMotion
                ? FadeOut.duration(tokens.motion.duration.exit)
                : FadeOutUp.duration(tokens.motion.duration.exit)
            }
            key={toast.id}
            style={[styles.position, { top: insets.top + tokens.space.sm }]}>
            <View style={styles.toast}>
              <View style={[styles.symbol, { backgroundColor: appearance.tint }]}>
                <Glyph color={appearance.color} name={appearance.symbol} size={17} />
              </View>
              <View style={styles.copy}>
                <Text variant="subhead">{toast.title}</Text>
                {toast.message ? (
                  <Text style={styles.message} tone="secondary" variant="footnote">
                    {toast.message}
                  </Text>
                ) : null}
              </View>
              <Touchable
                accessibilityLabel="Dismiss notification"
                accessibilityRole="button"
                feedback="opacity"
                hitSlop={8}
                onPress={dismissToast}
                style={styles.dismiss}>
                <Glyph color={tokens.color.text.tertiary} name="xmark" size={13} />
              </Touchable>
            </View>
          </Animated.View>
        ) : null}
      </View>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const value = useContext(ToastContext);
  if (!value) throw new Error('useToast must be used inside ToastProvider');
  return value;
}

const styles = StyleSheet.create({
  position: {
    position: 'absolute',
    left: tokens.space.base,
    right: tokens.space.base,
    zIndex: 100,
    alignItems: 'center',
  },
  toast: {
    width: '100%',
    maxWidth: 520,
    minHeight: 60,
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.md,
    paddingVertical: tokens.space.md,
    paddingLeft: tokens.space.md,
    paddingRight: tokens.space.sm,
    borderRadius: tokens.radius.xl,
    borderCurve: 'continuous',
    backgroundColor: tokens.color.bg.surface,
    ...tokens.elevation.floating,
  },
  symbol: {
    width: 34,
    height: 34,
    borderRadius: tokens.radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  copy: { flex: 1 },
  message: { marginTop: tokens.optical.nudge },
  dismiss: {
    width: tokens.layout.touch,
    height: tokens.layout.touch,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
