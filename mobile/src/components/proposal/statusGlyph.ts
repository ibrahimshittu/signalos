import type { GlyphName } from '@/components/ui/Glyph';
import type { ProposalStatus } from '@/domain/studio';

/**
 * A distinct glyph per decision state.
 *
 * Two states that share a colour must not share a shape, otherwise the badge
 * is back to relying on colour alone.
 */
const symbols: Record<ProposalStatus, GlyphName> = {
  available: 'clock',
  rejected: 'hand.raised',
  expired: 'clock.badge.xmark',
  submitted: 'paperplane',
  invalidated: 'exclamationmark.triangle.fill',
  archived: 'archivebox',
};

export function statusGlyph(status: ProposalStatus): GlyphName {
  return symbols[status] ?? 'questionmark.circle.fill';
}
