import { Image, StyleSheet, View } from 'react-native';

/** Bundled artwork: no remote image request, no motion, no financial meaning. */
export function StudioBackdrop({ prominent = false }: { prominent?: boolean }) {
  return (
    <View
      pointerEvents="none"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={StyleSheet.absoluteFill}
    >
      <Image
        accessible={false}
        source={require('../../../assets/images/studio-architecture.png')}
        resizeMode="cover"
        style={[StyleSheet.absoluteFill, styles.image, { opacity: prominent ? 1 : 0.045 }]}
      />
      {prominent ? <View style={[StyleSheet.absoluteFill, styles.veil]} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  image: { width: '100%', height: '100%' },
  veil: { backgroundColor: 'rgba(244,245,247,0.28)' },
});
