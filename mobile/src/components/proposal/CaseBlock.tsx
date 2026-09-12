import { StyleSheet, View } from 'react-native';
import { Glyph, Text } from '@/components/ui';
import type { GlyphName } from '@/components/ui/Glyph';
import { tokens } from '@/theme/tokens';

export type CaseTone = 'support' | 'against' | 'fit' | 'reject';

const marks: Record<CaseTone, { symbol: GlyphName; color: string }> = {
  support: { symbol: 'checkmark.circle', color: tokens.color.finance.gain },
  against: { symbol: 'exclamationmark.circle', color: tokens.color.finance.loss },
  fit: { symbol: 'chart.pie', color: tokens.color.accent.base },
  reject: { symbol: 'hand.raised', color: tokens.color.status.caution },
};

interface Props {
  title: string;
  body: string;
  tone: CaseTone;
}

/**
 * One side of the argument.
 *
 * The case for and the case against use identical typography and weight — the
 * opposing case is a peer of the thesis, never a disclaimer beneath it.
 */
export function CaseBlock({ body, title, tone }: Props) {
  const mark = marks[tone];
  return (
    <View style={styles.block}>
      <View style={styles.heading}>
        <Glyph color={mark.color} name={mark.symbol} size={16} />
        <Text style={styles.title} variant="headline">
          {title}
        </Text>
      </View>
      <Text style={styles.body} tone="secondary" variant="callout">
        {body}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  block: { marginTop: tokens.space.lg },
  heading: { flexDirection: 'row', alignItems: 'center', gap: tokens.space.sm },
  title: { flex: 1 },
  body: { marginTop: tokens.space.sm },
});
