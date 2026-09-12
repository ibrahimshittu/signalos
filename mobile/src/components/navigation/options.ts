import type { NativeStackNavigationOptions } from 'expo-router';
import { tokens } from '@/theme/tokens';

/**
 * Shared options for every stack inside a tab.
 *
 * The header is left to the platform. A transparent bar is all iOS 26 needs to
 * apply its own scroll edge effect and render the chrome as Liquid Glass, and
 * it keeps the large-title collapse, back gesture, and scroll-to-top behaviour
 * we would otherwise have to reimplement.
 *
 * `headerBlurEffect` is deliberately absent: setting it stacks a second
 * material on top of the scroll edge effect, which RNScreens warns about and
 * which reads as a muddy double blur at the boundary.
 */
export const stackScreenOptions: NativeStackNavigationOptions = {
  headerTransparent: true,
  headerShadowVisible: false,
  headerLargeTitleShadowVisible: false,
  headerLargeStyle: { backgroundColor: 'transparent' },
  headerTitleStyle: { color: tokens.color.text.primary },
  headerLargeTitleStyle: { color: tokens.color.text.primary },
  headerTintColor: tokens.color.accent.base,
  headerBackButtonDisplayMode: 'minimal',
  contentStyle: { backgroundColor: tokens.color.bg.canvas },
};

/** A tab's root screen: large title, collapsing into the glass bar on scroll. */
export const rootScreenOptions: NativeStackNavigationOptions = {
  headerLargeTitle: true,
};
