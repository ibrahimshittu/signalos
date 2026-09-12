import { StyleSheet, View } from 'react-native';
import { Card, Glyph, ProviderMark, StatusBadge, Text, Touchable } from '@/components/ui';
import type { ConnectionHealth } from '@/domain/connection';
import { providerName } from '@/domain/connection';
import type { BrokerConnection } from '@/domain/studio';
import { tokens } from '@/theme/tokens';

interface Props {
  connection: BrokerConnection | null;
  health: ConnectionHealth;
  onPress(): void;
}

/**
 * Shown only when the provider connection needs the user to do something.
 *
 * A healthy connection is not news, and a permanent provider card on the home
 * screen makes an Account concern compete with the portfolio. When everything
 * is working, provenance lives as one quiet line under the balance; this card
 * appears only when the answer to "is my data good?" is no.
 */
export function ConnectionAlert({ connection, health, onPress }: Props) {
  const provider = providerName(connection?.provider_id);

  return (
    <Card style={styles.card}>
      <Touchable
        accessibilityHint="Opens connection settings"
        accessibilityLabel={`${provider} connection, ${health.label}. ${health.meaning}`}
        accessibilityRole="button"
        feedback="highlight"
        highlightRadius={0}
        onPress={onPress}
        style={styles.body}>
        <View style={styles.identity}>
          <ProviderMark displayName={provider} providerId={connection?.provider_id ?? 'unknown'} size={36} />
          <Text style={styles.name} variant="headline">
            {provider}
          </Text>
          <StatusBadge label={health.label} tone={health.tone} />
          <Glyph color={tokens.color.text.tertiary} name="chevron.right" size={13} />
        </View>
        <Text tone="secondary" variant="footnote">
          {health.meaning}
        </Text>
      </Touchable>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: tokens.space.xl },
  body: { padding: tokens.space.base, gap: tokens.space.md },
  identity: { flexDirection: 'row', alignItems: 'center', gap: tokens.space.md },
  name: { flex: 1 },
});
