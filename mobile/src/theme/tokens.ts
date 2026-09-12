import type { TextStyle, ViewStyle } from 'react-native';

/**
 * SignalOS design tokens.
 *
 * Every visual value in the app comes from here. Screens compose tokens; they
 * never introduce their own sizes, colours, durations, or radii.
 *
 * See docs/design/2026-08-14-signalos-design-system.md for the reasoning.
 */

/* ------------------------------------------------------------------ colour */

/**
 * Neutral light canvas, deep graphite text, one restrained accent.
 *
 * Green and red are financial semantics only: they mean money moved, or a
 * connection is healthy or failed. They never mean "good option".
 *
 * Contrast of every foreground/background pair is asserted in tokens.test.ts.
 */
const color = {
  bg: {
    /**
     * The default ground. Deliberately a shade below white so a surface can
     * read as raised without needing a heavy border or shadow.
     */
    canvas: '#F4F5F7',
    /** A raised block. Used selectively — not every section is a surface. */
    surface: '#FFFFFF',
    /** Recessed fills: segmented tracks, skeletons, meters. */
    sunken: '#E9EBEF',
    /** Behind modals and sheets. */
    scrim: 'rgba(12,15,20,0.34)',
  },
  text: {
    primary: '#15181C',
    secondary: '#585F68',
    tertiary: '#626971',
    /** On accent or dark fills. */
    inverse: '#FFFFFF',
  },
  border: {
    /** 1px structure between peers on the canvas. */
    hairline: '#DFE3E8',
    /** Separators inside a surface, where the ground is already white. */
    separator: '#E7EAEE',
    /** Inputs and outline controls. */
    strong: '#C8CDD5',
  },
  /** The single brand accent. Marks focus and the primary action — nothing else. */
  accent: {
    base: '#1A4E8A',
    pressed: '#143D6D',
    tint: '#E8EEF7',
  },
  /** Reserved for actual gain, loss, and flat performance. */
  finance: {
    gain: '#0F6B4C',
    gainTint: '#E3F0EA',
    loss: '#B3251C',
    lossTint: '#FBE7E5',
    flat: '#585F68',
  },
  /** Non-financial system status. */
  status: {
    caution: '#8A5300',
    cautionTint: '#F8EDDC',
    info: '#1A4E8A',
    infoTint: '#E8EEF7',
  },
  /** Opaque stand-in used when Reduce Transparency is enabled. */
  materialFallback: '#FAFBFC',
} as const;

/* ----------------------------------------------------------------- spacing */

/** 8-point system. `xs` is the only half-step. */
const space = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  xxxl: 40,
  huge: 48,
  section: 56,
} as const;

/**
 * Sub-grid adjustments. These are not spacing — they are optical corrections
 * for aligning a glyph to a cap height or nudging a baseline, where the 4pt
 * step is visibly too coarse. Never use them for layout rhythm.
 */
const optical = {
  hair: 1,
  nudge: 2,
  tick: 3,
} as const;

/* ------------------------------------------------------------------ layout */

const layout = {
  /** Horizontal screen margin. */
  gutter: 24,
  /** Keeps line length readable on large devices. */
  contentMax: 640,
  /** Minimum touch target, enforced by primitives. */
  touch: 44,
  /** Standard control height. */
  control: 50,
  /** Compact control height — still above the touch minimum. */
  controlCompact: 44,
  /** Clearance under scroll content so the tab bar never covers anything. */
  tabBarClearance: 28,
} as const;

/**
 * Restrained radius scale, paired to control height so the curve stays
 * proportionate: chips at 26pt take `sm`, 50pt controls take `lg`.
 * `full` exists only for dots, bars, and meters — never for buttons.
 */
const radius = {
  sm: 10,
  md: 12,
  lg: 14,
  xl: 16,
  /**
   * Floating sheets only. A sheet is a large surface with nothing beside it,
   * so it carries a deeper curve than any control without reading as a pill.
   */
  sheet: 30,
  full: 999,
} as const;

/* -------------------------------------------------------------- typography */

/**
 * The platform font: SF Pro on iOS, Roboto on Android. Omitting `fontFamily`
 * is what selects it, and is also what lets Dynamic Type do optical sizing.
 *
 * Sentence case only — no uppercase labels, no positive letter-spacing.
 */
const type = {
  /** A single money figure per screen. Tightest leading and tracking. */
  hero: { fontSize: 34, lineHeight: 38, fontWeight: '700', letterSpacing: -0.9 },
  display: { fontSize: 32, lineHeight: 36, fontWeight: '700', letterSpacing: -0.7 },
  title1: { fontSize: 26, lineHeight: 30, fontWeight: '700', letterSpacing: -0.5 },
  title2: { fontSize: 21, lineHeight: 26, fontWeight: '600', letterSpacing: -0.35 },
  title3: { fontSize: 18, lineHeight: 23, fontWeight: '600', letterSpacing: -0.2 },
  headline: { fontSize: 16, lineHeight: 21, fontWeight: '600', letterSpacing: -0.1 },
  body: { fontSize: 16, lineHeight: 23, fontWeight: '400' },
  callout: { fontSize: 15, lineHeight: 21, fontWeight: '400' },
  subhead: { fontSize: 14, lineHeight: 19, fontWeight: '500' },
  footnote: { fontSize: 13, lineHeight: 18, fontWeight: '400' },
  /**
   * The smallest permitted size, and the only one with positive tracking —
   * small text needs the letters opened up slightly to stay legible.
   */
  caption: { fontSize: 12, lineHeight: 16, fontWeight: '500', letterSpacing: 0.1 },
} as const satisfies Record<string, TextStyle>;

/**
 * Dynamic Type is honoured, but two-column money rows break past roughly 1.8x.
 * Capping there keeps the largest accessibility sizes usable instead of broken.
 */
const maxFontSizeMultiplier = 1.8;

/** Applied to every number so columns align and values don't jitter on refresh. */
const tabular = { fontVariant: ['tabular-nums'] } as const satisfies TextStyle;

/* ------------------------------------------------------------------ motion */

/**
 * Immediate and physical. Transform and opacity only, critically damped, and
 * every ordinary transition stays under 300ms.
 */
const motion = {
  duration: {
    /** Press feedback begins on touch-down, and lands almost immediately. */
    pressIn: 100,
    /** Release is slightly slower than the press, so it settles rather than snaps. */
    pressOut: 160,
    state: 180,
    enter: 240,
    exit: 160,
    /** Between staggered siblings. Long enough to read, short enough to ignore. */
    stagger: 45,
  },
  easing: {
    /**
     * Entering and responding. The stock CSS curves are too weak to read as
     * intentional; this one moves immediately, which is the frame the user is
     * watching most closely.
     */
    out: [0.23, 1, 0.32, 1] as const,
    /** Moving or morphing on screen, where both ends need acceleration. */
    inOut: [0.77, 0, 0.175, 1] as const,
  },
  /** Subtle enough to feel like pressure, not like a shrinking button. */
  pressScale: 0.97,
  /** Entrance offset. Any further reads as a slide rather than a settle. */
  enterOffset: 10,
} as const;

/* --------------------------------------------------------------- elevation */

/**
 * Three levels. Most of the app is level 0 — hierarchy comes from whitespace,
 * alignment, and typography rather than from shadows and boxes.
 */
const elevation = {
  /** Flat on the canvas. Most of the app lives here. */
  flat: {} as ViewStyle,
  /**
   * A grouped block. It reads as raised because the canvas sits below white,
   * so it needs only the faintest shadow — no border competing with the
   * separators inside it.
   */
  surface: {
    backgroundColor: color.bg.surface,
    borderRadius: radius.lg,
    borderCurve: 'continuous',
    boxShadow: '0 1px 2px rgba(16,24,40,0.04), 0 0 0 0.5px rgba(16,24,40,0.05)',
  } as ViewStyle,
  /** Genuinely floating over content: the approval tray and system chrome. */
  floating: {
    boxShadow: '0 8px 28px rgba(14,20,30,0.14), 0 2px 6px rgba(14,20,30,0.06)',
  } as ViewStyle,
} as const;

export const tokens = {
  color,
  space,
  optical,
  layout,
  radius,
  type,
  tabular,
  maxFontSizeMultiplier,
  motion,
  elevation,
} as const;

export type Tokens = typeof tokens;
export type TypeVariant = keyof typeof type;

/** Semantic colour for a signed change. Always paired with a sign and a glyph. */
export function colorForChange(value: number): string {
  if (value > 0) return color.finance.gain;
  if (value < 0) return color.finance.loss;
  return color.finance.flat;
}
