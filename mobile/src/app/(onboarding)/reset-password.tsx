import { useState } from 'react';
import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { Button, Callout, Field, FlowScreen, Text } from '@/components/ui';
import { useAuth } from '@/services/auth/AuthProvider';
import { tokens } from '@/theme/tokens';

export default function ResetPasswordScreen() {
  const { session, updatePassword } = useAuth();
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const passwordError = password.length < 8 ? 'Use at least 8 characters.' : undefined;
  const confirmationError = password !== confirmation ? 'The passwords do not match.' : undefined;

  const submit = async () => {
    setSubmitted(true);
    if (!session || passwordError || confirmationError) return;
    setLoading(true);
    setError(null);
    try {
      await updatePassword(password);
      router.replace('/');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Your password could not be changed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <FlowScreen
      footer={
        <View style={styles.footer}>
          <Button loading={loading} onPress={() => void submit()} title="Save new password" />
          {!session ? (
            <Button
              onPress={() => router.replace('/forgot-password')}
              title="Request a new link"
              variant="tertiary"
            />
          ) : null}
        </View>
      }
      topInset={false}
    >
      <Text accessibilityRole="header" variant="title1">
        Choose a new password
      </Text>
      <Text style={styles.lede} tone="secondary" variant="callout">
        Use a password you have not used for another account.
      </Text>

      <View style={styles.fields}>
        {!session ? (
          <Callout
            body="This recovery session is missing or expired. Request a new reset link."
            live
            title="Reset link required"
            tone="caution"
          />
        ) : null}
        {error ? <Callout body={error} live title="Password not changed" tone="caution" /> : null}
        <Field
          autoCapitalize="none"
          autoComplete="new-password"
          error={submitted ? passwordError : undefined}
          label="New password"
          onChangeText={setPassword}
          secureTextEntry
          textContentType="newPassword"
          value={password}
        />
        <Field
          autoCapitalize="none"
          autoComplete="new-password"
          error={submitted ? confirmationError : undefined}
          label="Confirm new password"
          onChangeText={setConfirmation}
          secureTextEntry
          textContentType="newPassword"
          value={confirmation}
        />
      </View>
    </FlowScreen>
  );
}

const styles = StyleSheet.create({
  lede: { marginTop: tokens.space.sm, maxWidth: 460 },
  fields: { gap: tokens.space.lg, marginTop: tokens.space.xl },
  footer: { gap: tokens.space.xs },
});
