import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, Callout, Field, FlowScreen, Text } from '@/components/ui';
import * as haptics from '@/lib/haptics';
import { useAuth } from '@/services/auth/AuthProvider';
import { useAppStore } from '@/store/useAppStore';
import { tokens } from '@/theme/tokens';

const CODE_LENGTH = 6;

export default function VerifyScreen() {
  const email = useAppStore((state) => state.account.email);
  const { resendVerification, session, verifyEmail } = useAuth();
  const [code, setCode] = useState('');
  const [resent, setResent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session) router.replace('/studio');
  }, [session]);

  const submit = async () => {
    if (code.length !== CODE_LENGTH) return;
    setLoading(true);
    setError(null);
    try {
      await verifyEmail(email, code);
      haptics.success();
      router.replace('/studio');
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Email verification could not be completed.',
      );
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setLoading(true);
    setError(null);
    try {
      await resendVerification(email);
      setCode('');
      setResent(true);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'A new verification email could not be sent.',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <FlowScreen
      footer={
        <View style={styles.footer}>
          <Button
            disabled={code.length !== CODE_LENGTH || !email}
            loading={loading}
            onPress={() => void submit()}
            title="Verify email"
          />
          <Button
            disabled={!email}
            onPress={() => void resend()}
            title={resent ? 'Send another code' : 'I did not get a code'}
            variant="tertiary"
          />
        </View>
      }
      topInset={false}
    >
      <Text accessibilityRole="header" variant="title1">
        Confirm your email
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        Open the confirmation link in the email sent to {email || 'your email address'}, or enter
        its {CODE_LENGTH}-digit code here.
      </Text>

      <View style={styles.fields}>
        {error ? <Callout body={error} live title="Email not verified" tone="caution" /> : null}
        <Field
          autoFocus
          keyboardType="number-pad"
          label="Verification code"
          maxLength={CODE_LENGTH}
          numeric
          onChangeText={(value) => setCode(value.replace(/\D/g, ''))}
          placeholder="000000"
          textContentType="oneTimeCode"
          value={code}
        />
        {resent ? (
          <Text accessibilityLiveRegion="polite" tone="secondary" variant="footnote">
            A new confirmation email is on its way. Use its newest link or code.
          </Text>
        ) : null}
      </View>
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  lede: { marginTop: tokens.space.sm, maxWidth: 460 },
  fields: { gap: tokens.space.md, marginTop: tokens.space.xl },
  footer: { gap: tokens.space.xs },
});
