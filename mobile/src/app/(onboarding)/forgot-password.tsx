import { useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, Callout, Field, FlowScreen, Text } from '@/components/ui';
import { useAuth } from '@/services/auth/AuthProvider';
import { tokens } from '@/theme/tokens';

const EMAIL = /^\S+@\S+\.\S+$/;

export default function ForgotPasswordScreen() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const emailError = EMAIL.test(email) ? undefined : 'Enter the email address on your account.';

  const submit = async () => {
    setSubmitted(true);
    if (emailError) return;
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The reset email could not be sent.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <FlowScreen
      footer={
        <View style={styles.footer}>
          <Button
            loading={loading}
            onPress={() => void submit()}
            title={sent ? 'Send again' : 'Send reset link'}
          />
          <Button onPress={() => router.back()} title="Back to sign in" variant="tertiary" />
        </View>
      }
      topInset={false}
    >
      <Text accessibilityRole="header" variant="title1">
        Reset your password
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        We will email a reset link if an account exists for this address.
      </Text>

      <View style={styles.fields}>
        {error ? <Callout body={error} live title="Email not sent" tone="caution" /> : null}
        <Field
          autoCapitalize="none"
          autoComplete="email"
          error={submitted ? emailError : undefined}
          keyboardType="email-address"
          label="Email address"
          onChangeText={setEmail}
          textContentType="emailAddress"
          value={email}
        />
        {sent ? (
          <Callout
            body="Follow the link in the email to choose a new password. It expires in 30 minutes."
            live
            title="Check your inbox"
            tone="positive"
          />
        ) : null}
      </View>
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  lede: { marginTop: tokens.space.sm, maxWidth: 460 },
  fields: { gap: tokens.space.lg, marginTop: tokens.space.xl },
  footer: { gap: tokens.space.xs },
});
