import { useMemo } from 'react';
import { View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, Defs, Line, LinearGradient, Path, Stop } from 'react-native-svg';
import { colorForChange, tokens } from '@/theme/tokens';

interface Props {
  /** Chronological values. Fewer than two renders nothing — no invented shape. */
  values: number[];
  width: number;
  height?: number;
  /** Spoken summary. The line itself carries no meaning for VoiceOver. */
  label: string;
  style?: StyleProp<ViewStyle>;
}



const STROKE = 2;
/** Radius of the end dot plus its halo — the widest thing drawn. */
const CAP = 4;
/** Keeps the stroke, the end cap, and its halo fully inside the box. */
const INSET = CAP + 1;

/**
 * The retained equity history, drawn at the size of a caption.
 *
 * It exists to give the balance a shape, not to be read precisely — there are
 * no axes, no gridlines, and no tooltip, because a number that matters is
 * already stated above it in full.
 */
export function Sparkline({ height = 44, label, style, values, width }: Props) {
  const geometry = useMemo(() => {
    if (values.length < 2 || width <= 0) return null;

    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const stepX = (width - CAP * 2) / (values.length - 1);

    const points = values.map((value, index) => ({
      x: CAP + index * stepX,
      y: INSET + (1 - (value - min) / span) * (height - INSET * 2),
    }));

    // A monotone-ish smoothing: horizontal control points keep the curve from
    // overshooting past a local extreme, which would misrepresent the data.
    const line = points
      .map((point, index) => {
        if (index === 0) return `M${point.x},${point.y}`;
        const previous = points[index - 1];
        const midX = (previous.x + point.x) / 2;
        return `C${midX},${previous.y} ${midX},${point.y} ${point.x},${point.y}`;
      })
      .join(' ');

    return {
      line,
      area: `${line} L${points[points.length - 1].x},${height} L${points[0].x},${height} Z`,
      last: points[points.length - 1],
      // Where the period opened. Without it the curve only shows shape; with
      // it, the same curve shows whether the balance is above or below where
      // it started, which is the question the figure above is answering.
      baseline: points[0].y,
    };
  }, [height, values, width]);

  if (!geometry) return <View style={[{ width, height }, style]} />;

  const tint = colorForChange(values[values.length - 1] - values[0]);

  return (
    <View accessibilityLabel={label} accessible style={style}>
      <Svg height={height} width={width}>
        <Defs>
          <LinearGradient id="sparklineFade" x1="0" x2="0" y1="0" y2="1">
            <Stop offset="0" stopColor={tint} stopOpacity={0.16} />
            <Stop offset="1" stopColor={tint} stopOpacity={0} />
          </LinearGradient>
        </Defs>
        <Path d={geometry.area} fill="url(#sparklineFade)" />
        <Line
          stroke={tokens.color.border.strong}
          strokeDasharray="2 3"
          strokeWidth={1}
          x1={0}
          x2={width}
          y1={geometry.baseline}
          y2={geometry.baseline}
        />
        <Path
          d={geometry.line}
          fill="none"
          stroke={tint}
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={STROKE}
        />
        {/* A halo keeps the end point legible where the line doubles back on itself. */}
        <Circle cx={geometry.last.x} cy={geometry.last.y} fill={tokens.color.bg.canvas} r={4} />
        <Circle cx={geometry.last.x} cy={geometry.last.y} fill={tint} r={2.5} />
      </Svg>
    </View>
  );
}
