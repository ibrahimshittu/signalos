import { type PropsWithChildren, type ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  View,
  type ScrollViewProps,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import Animated, { type AnimatedScrollViewProps } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { tokens } from '@/theme/tokens';
import { StudioBackdrop } from './StudioBackdrop';

interface ScreenProps {
  /**
   * Must stay the route's first child so the native header and tab bar can
   * apply their own content insets and large-title collapse.
   */
  refreshControl?: ScrollViewProps['refreshControl'];
  contentStyle?: StyleProp<ViewStyle>;
  /**
   * A Reanimated scroll handler. Runs on the UI thread, so a header that
   * responds to scroll never waits on a JavaScript round trip.
   */
  onScroll?: AnimatedScrollViewProps['onScroll'];
  children: ReactNode;
}

/**
 * A scrolling screen inside a native Stack.
 *
 * `contentInsetAdjustmentBehavior="automatic"` is what lets iOS place content
 * under the glass header and above the tab bar without any manual offsets.
 */
export function Screen({ children, contentStyle, onScroll, refreshControl }: ScreenProps) {
  return (
    <Animated.ScrollView
      automaticallyAdjustKeyboardInsets
      contentContainerStyle={[styles.content, contentStyle]}
      contentInsetAdjustmentBehavior="automatic"
      keyboardDismissMode={Platform.OS === 'ios' ? 'interactive' : 'on-drag'}
      keyboardShouldPersistTaps="handled"
      onScroll={onScroll}
      refreshControl={refreshControl}
      scrollEventThrottle={16}
      style={styles.scroll}
    >
      <StudioBackdrop />
      <View style={styles.column}>{children}</View>
    </Animated.ScrollView>
  );
}

interface FlowScreenProps {
  background?: ReactNode;
  /** Sticky action area. Stays reachable without scrolling on small devices. */
  footer?: ReactNode;
  header?: ReactNode;
  children: ReactNode;
  contentStyle?: StyleProp<ViewStyle>;
  /** Off when a native header already occupies the top safe area. */
  topInset?: boolean;
}

/**
 * A screen for linear flows (onboarding, approval): scrolling content with a
 * pinned footer, outside any native header.
 */
export function FlowScreen({
  background,
  children,
  contentStyle,
  footer,
  header,
  topInset = true,
}: FlowScreenProps) {
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      style={[styles.flow, { paddingTop: topInset ? insets.top : 0 }]}
    >
      {background ?? <StudioBackdrop />}
      {header ? <View style={styles.flowHeader}>{header}</View> : null}
      <ScrollView
        automaticallyAdjustKeyboardInsets
        contentContainerStyle={[styles.flowContent, contentStyle]}
        keyboardDismissMode={Platform.OS === 'ios' ? 'interactive' : 'on-drag'}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
        style={[styles.scroll, styles.transparent]}
      >
        <View style={styles.column}>{children}</View>
      </ScrollView>
      {footer ? (
        <View
          style={[styles.footer, { paddingBottom: Math.max(insets.bottom, tokens.space.base) }]}
        >
          <View style={styles.column}>{footer}</View>
        </View>
      ) : null}
    </KeyboardAvoidingView>
  );
}

/** Horizontal rhythm for anything rendered outside `Screen`. */
export function Gutter({ children, style }: PropsWithChildren<{ style?: StyleProp<ViewStyle> }>) {
  return <View style={[styles.gutter, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  transparent: { backgroundColor: 'transparent' },
  scroll: { flex: 1, backgroundColor: tokens.color.bg.canvas },
  content: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.md,
    paddingBottom: tokens.space.section + tokens.layout.tabBarClearance,
  },
  column: { width: '100%', maxWidth: tokens.layout.contentMax, alignSelf: 'center' },
  flow: { flex: 1, backgroundColor: tokens.color.bg.canvas },
  flowHeader: { paddingHorizontal: tokens.layout.gutter, paddingTop: tokens.space.sm },
  flowContent: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.lg,
    paddingBottom: tokens.space.xxl,
    flexGrow: 1,
  },
  footer: {
    paddingHorizontal: tokens.layout.gutter,
    paddingTop: tokens.space.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: tokens.color.border.hairline,
    backgroundColor: tokens.color.bg.canvas,
  },
  gutter: { paddingHorizontal: tokens.layout.gutter },
});
