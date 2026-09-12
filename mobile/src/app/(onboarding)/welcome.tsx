import { router } from 'expo-router';
import { StyleSheet, View, useWindowDimensions } from 'react-native';
import { StudioBackdrop } from '@/components/ui/StudioBackdrop';
import { Button, FlowScreen, Glyph, Reveal, Text, Wordmark } from '@/components/ui';
import { tokens } from '@/theme/tokens';

/**
 * A quiet first impression. Product detail belongs in onboarding, after the
 * user chooses to begin.
 */
export default function WelcomeScreen() {
  const { height } = useWindowDimensions();
  return (
    <FlowScreen
      background={<StudioBackdrop prominent />}
      contentStyle={styles.content}
      footer={
        <View style={styles.footer}>
          <Button
            icon="arrow.right"
            onPress={() => router.push('/sign-up')}
            title="Create an account"
          />
          <Button onPress={() => router.push('/sign-in')} title="Sign in" variant="tertiary" />
          <Text center style={styles.legal} tone="tertiary" variant="caption">
            Investing involves risk, including loss of principal.
          </Text>
        </View>
      }
    >
      <Reveal>
        <Wordmark size={32} />
      </Reveal>

      <Reveal index={1}>
        <View style={[styles.hero, { marginTop: Math.max(96, Math.min(240, height * 0.23)) }]}>
          <Text accessibilityRole="header" style={styles.heading} variant="display">
            Market intelligence.{'\n'}
            <Text style={styles.heading} tone="accent" variant="display">
              Accountable to you.
            </Text>
          </Text>
          <Text style={styles.lede} tone="secondary" variant="body">
            A clearer view of the market, shaped around your portfolio.
          </Text>
        </View>
        <View style={styles.principle}>
          <Glyph color={tokens.color.accent.base} name="hand.raised" size={22} />
          <View style={styles.principleCopy}>
            <Text variant="headline">Your portfolio. Your call.</Text>
            <Text tone="secondary" variant="footnote">
              Analysis first. Orders only with your approval.
            </Text>
          </View>
        </View>
      </Reveal>
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  content: { paddingTop: tokens.space.xxl },
  hero: {
    maxWidth: 480,
    padding: tokens.space.xl,
    backgroundColor: 'rgba(244,245,247,0.96)',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
  },
  heading: { fontSize: 34, lineHeight: 38, letterSpacing: -1 },
  lede: { marginTop: tokens.space.base, maxWidth: 420 },
  footer: { gap: tokens.space.xs },
  legal: { marginTop: tokens.space.sm, alignSelf: 'center', maxWidth: 460 },
  principle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: tokens.space.md,
    padding: tokens.space.xl,
    paddingTop: 0,
    backgroundColor: 'rgba(244,245,247,0.96)',
    borderBottomLeftRadius: 24,
    borderBottomRightRadius: 24,
  },
  principleCopy: { flex: 1, gap: tokens.space.xs },
});
