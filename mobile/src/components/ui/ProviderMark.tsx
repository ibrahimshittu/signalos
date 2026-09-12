import { Image, StyleSheet, View, type ImageSourcePropType } from 'react-native';
import { Text } from './Text';
import { tokens } from '@/theme/tokens';

/**
 * Official provider artwork, keyed by the id the API returns.
 *
 * These are square brand avatars, so the tile renders them edge to edge and
 * clips them to its own radius rather than insetting them in a neutral chip —
 * a logo floating inside a second container reads as a placeholder.
 *
 * Each is a third-party trademark used to identify a connected account. Replace
 * with the asset from the provider's own brand page before shipping, and check
 * their brand terms.
 */
const marks: Record<string, ImageSourcePropType | undefined> = {
  bybit: require('../../../assets/providers/bybit.png'),
};

interface Props {
  providerId: string;
  displayName: string;
  size?: number;
}

/**
 * The provider's identity, in a tile.
 *
 * A mark in a defined container is what makes a connection read as a real
 * institutional link rather than a settings row — so the tile, its radius, and
 * its optical weight stay fixed whether or not the artwork exists.
 */
export function ProviderMark({ displayName, providerId, size = 40 }: Props) {
  const source = marks[providerId];
  // Keeps the corner proportionate to the tile at any size, matching the way
  // the radius scale pairs to control height elsewhere.
  const radius = Math.round(size * 0.29);
  const shape = { width: size, height: size, borderRadius: radius };

  if (source) {
    return (
      <View accessibilityLabel={displayName} accessibilityRole="image" style={[styles.artwork, shape]}>
        <Image resizeMode="cover" source={source} style={shape} />
      </View>
    );
  }

  return (
    <View accessibilityLabel={displayName} accessibilityRole="image" style={[styles.tile, shape]}>
      {/* A capital letter sits high in its own line box; this recentres it. */}
      <Text style={styles.monogram} variant="title3">
        {displayName.charAt(0).toUpperCase()}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  artwork: { overflow: 'hidden', borderCurve: 'continuous' },
  tile: {
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: tokens.color.bg.sunken,
    borderCurve: 'continuous',
  },
  monogram: { marginTop: -tokens.optical.hair },
});
