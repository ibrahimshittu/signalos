import { useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, Callout, Field, FlowScreen, Text } from '@/components/ui';
import { useAuth } from '@/services/auth/AuthProvider';
import { tokens } from '@/theme/tokens';

const EMAIL = /^\S+@\S+\.\S+$/;

export default function SignUpScreen() {
  const { signUp } = useAuth();
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameError =
    !firstName.trim() || !lastName.trim() ? 'Enter your first and last name.' : undefined;
  const emailError = EMAIL.test(email)
    ? undefined
    : 'Enter an email address such as name@example.com.';
  const passwordError = password.length < 8 ? 'Use at least 8 characters.' : undefined;
  const valid = !nameError && !emailError && !passwordError;

  const submit = async () => {
    setSubmitted(true);
    if (!valid) return;
    setLoading(true);
    setError(null);
    try {
      const result = await signUp({ firstName, lastName, email, password });
      router.replace(result.verificationRequired ? '/verify' : '/profile');
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Account creation could not be completed.',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <FlowScreen
      footer={
        <View style={styles.footer}>
          <Button loading={loading} onPress={() => void submit()} title="Create account" />
          <Text center tone="tertiary" variant="caption">
            You will receive security and account messages by email.
          </Text>
        </View>
      }
      topInset={false}
    >
      <Text accessibilityRole="header" variant="title1">
        Create your account
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        A few details to make this your studio.
      </Text>

      <View style={styles.fields}>
        {error ? <Callout body={error} live title="Account not created" tone="caution" /> : null}
        <Field
          autoComplete="given-name"
          error={submitted ? nameError : undefined}
          label="First name"
          onChangeText={setFirstName}
          textContentType="givenName"
          value={firstName}
        />
        <Field
          autoComplete="family-name"
          label="Last name"
          onChangeText={setLastName}
          textContentType="familyName"
          value={lastName}
        />
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
          autoComplete="new-password"
          error={submitted ? passwordError : undefined}
          hint="At least 8 characters. Use a unique password."
          label="Password"
          onChangeText={setPassword}
          secureTextEntry
          textContentType="newPassword"
          value={password}
        />
      </View>
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  lede: { marginTop: tokens.space.sm, maxWidth: 460 },
  fields: { gap: tokens.space.lg, marginTop: tokens.space.xl },
  footer: { gap: tokens.space.md },
});
