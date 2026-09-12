import { useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, Callout, Field, FlowScreen, Text } from '@/components/ui';
import { useAuth } from '@/services/auth/AuthProvider';
import { tokens } from '@/theme/tokens';

const EMAIL = /^\S+@\S+\.\S+$/;

export default function SignInScreen() {
  const { callbackError, clearCallbackError, signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailError = EMAIL.test(email) ? undefined : 'Enter the email address on your account.';
  const passwordError = password.length === 0 ? 'Enter your password.' : undefined;

  const submit = async () => {
    setSubmitted(true);
    if (emailError || passwordError) return;
    setLoading(true);
    setError(null);
    clearCallbackError();
    try {
      await signIn(email, password);
      router.replace('/studio');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Sign in could not be completed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <FlowScreen
      footer={
        <View style={styles.footer}>
          <Button loading={loading} onPress={() => void submit()} title="Sign in" />
          <Button
            onPress={() => router.push('/forgot-password')}
            title="Forgot password"
            variant="tertiary"
          />
        </View>
      }
      topInset={false}
    >
      <Text accessibilityRole="header" variant="title1">
        Welcome back
      </Text>

      <View style={styles.fields}>
        {error || callbackError ? (
          <Callout
            body={error ?? callbackError ?? ''}
            live
            title="Unable to sign in"
            tone="caution"
          />
        ) : null}
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
        <Field
          autoCapitalize="none"
          autoComplete="current-password"
          error={submitted ? passwordError : undefined}
          label="Password"
          onChangeText={setPassword}
          secureTextEntry
          textContentType="password"
          value={password}
        />
      </View>
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  fields: { gap: tokens.space.lg, marginTop: tokens.space.xl },
  footer: { gap: tokens.space.xs },
});
