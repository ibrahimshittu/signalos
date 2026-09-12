import { StyleSheet, View } from 'react-native';
import { Card, CardRow, Glyph, Text } from '@/components/ui';
import { mandateReason, postureLabels } from '@/domain/mandate';
import type { AdaptiveRiskMandate } from '@/domain/studio';
import { formatRatioPct } from '@/lib/format';
import { tokens } from '@/theme/tokens';

interface Props {
  mandate: AdaptiveRiskMandate;
  /** Hidden on Account, where the framing has already been established. */
  showExplanation?: boolean;
}

/**
 * The adaptive mandate, presented as something the system derived.
 *
 * The posture leads at display weight because it is the conclusion; the
 * ceilings follow as a grouped list because they are its terms. The user never
 * sets a stop distance, position size, or leverage — this exists so those
 * decisions are inspectable, not so they can be configured.
 */
export function MandateSummary({ mandate, showExplanation = true }: Props) {
  return (
    <View style={styles.block}>
      <View>
        <Text tone="tertiary" variant="caption">
          Starting posture
        </Text>
        <Text style={styles.posture} variant="title1">
          {postureLabels[mandate.risk_posture]}
        </Text>
      </View>

      {showExplanation ? (
        <Text tone="secondary" variant="callout">
          Safety limits derived from your answers. Each proposal is checked against your portfolio
          and may use lower limits.
        </Text>
      ) : null}

      <Card>
        <CardRow
          detail="The most a single proposal may put at risk"
          label="Loss budget per trade"
          value={formatRatioPct(mandate.max_loss_per_trade_pct)}
        />
        <CardRow
          detail="Reference limit; automatic drawdown protection is not active yet"
          label="Drawdown reference"
          value={formatRatioPct(mandate.max_portfolio_drawdown_pct)}
        />
        <CardRow label="Leverage ceiling" value={`${mandate.max_leverage}×`} />
        <CardRow
          label="Derivatives"
          last
          numeric={false}
          value={mandate.derivatives_eligible ? 'Eligible, within limits' : 'Spot only'}
        />
      </Card>

      {mandate.reasons.length ? (
        <View style={styles.reasons}>
          <Text tone="tertiary" variant="caption">
            Why
          </Text>
          {mandate.reasons.map((reason) => (
            <View key={reason} style={styles.reason}>
              <Glyph
                color={tokens.color.text.tertiary}
                name="circle.fill"
                size={5}
                style={styles.bullet}
              />
              <Text style={styles.reasonText} tone="secondary" variant="footnote">
                {mandateReason(reason)}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  block: { gap: tokens.space.base },
  posture: { marginTop: tokens.optical.tick },
  reasons: { gap: tokens.space.sm },
  reason: { flexDirection: 'row', gap: tokens.space.sm, alignItems: 'flex-start' },
  // Centres a 5pt dot on the x-height of a 13pt line.
  bullet: { marginTop: 7 },
  reasonText: { flex: 1 },
});
