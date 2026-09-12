import { describe, expect, it } from '@jest/globals';
import { colorForChange, tokens } from './tokens';

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5]
    .map((offset) => parseInt(hex.slice(offset, offset + 2), 16) / 255)
    .map((value) => (value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4));
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(foreground: string, background: string): number {
  const a = relativeLuminance(foreground);
  const b = relativeLuminance(background);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const { color } = tokens;
const backgrounds = [color.bg.canvas, color.bg.surface, color.bg.sunken];
const foregrounds = [
  color.text.primary,
  color.text.secondary,
  color.text.tertiary,
  color.accent.base,
  color.accent.pressed,
  color.finance.gain,
  color.finance.loss,
  color.finance.flat,
  color.status.caution,
];

describe('colour contrast', () => {
  it.each(foregrounds)('%s meets AA body contrast on every background', (foreground) => {
    for (const background of backgrounds) {
      expect(contrast(foreground, background)).toBeGreaterThanOrEqual(4.5);
    }
  });

  it.each([
    ['accent', color.accent.base],
    ['accent pressed', color.accent.pressed],
    ['loss', color.finance.loss],
  ])('inverse text is readable on the %s fill', (_name, fill) => {
    expect(contrast(color.text.inverse, fill)).toBeGreaterThanOrEqual(4.5);
  });

  it.each([
    ['accent', color.accent.base, color.accent.tint],
    ['gain', color.finance.gain, color.finance.gainTint],
    ['loss', color.finance.loss, color.finance.lossTint],
    ['caution', color.status.caution, color.status.cautionTint],
  ])('%s reads against its own tint', (_name, foreground, tint) => {
    expect(contrast(foreground, tint)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(color.text.primary, tint)).toBeGreaterThanOrEqual(4.5);
  });
});

describe('semantic separation', () => {
  it('keeps the brand accent distinct from every financial and status meaning', () => {
    expect(color.accent.base).not.toBe(color.finance.gain);
    expect(color.accent.base).not.toBe(color.finance.loss);
    expect(color.accent.base).not.toBe(color.status.caution);
  });

  it('maps a signed change onto gain, loss, or flat', () => {
    expect(colorForChange(12.4)).toBe(color.finance.gain);
    expect(colorForChange(-0.01)).toBe(color.finance.loss);
    expect(colorForChange(0)).toBe(color.finance.flat);
  });
});

describe('scales', () => {
  it('keeps every spacing step on the 8-point grid, allowing one half-step', () => {
    for (const value of Object.values(tokens.space)) {
      expect(value % 8 === 0 || value % 8 === 4).toBe(true);
    }
  });

  it('keeps control radii inside the restrained 10-16pt scale', () => {
    const { full, sheet, ...controls } = tokens.radius;
    expect(full).toBeGreaterThan(100);
    for (const value of Object.values(controls)) {
      expect(value).toBeGreaterThanOrEqual(10);
      expect(value).toBeLessThanOrEqual(16);
    }
    // The sheet step sits above the control scale but well short of a capsule.
    expect(sheet).toBeGreaterThan(tokens.radius.xl);
    expect(sheet).toBeLessThan(36);
  });

  it('never sets type below 12pt, and keeps leading above the font size', () => {
    for (const style of Object.values(tokens.type)) {
      expect(style.fontSize).toBeGreaterThanOrEqual(12);
      expect(style.lineHeight).toBeGreaterThan(style.fontSize);
    }
  });

  it('tightens tracking as type grows and opens it only at the smallest size', () => {
    for (const style of Object.values(tokens.type)) {
      const tracking = (style as { letterSpacing?: number }).letterSpacing ?? 0;
      // Display sizes read too loose at default tracking and must be tightened;
      // reading sizes stay neutral; only the smallest size opens up.
      if (style.fontSize >= 18) expect(tracking).toBeLessThan(0);
      else if (style.fontSize >= 14) expect(tracking).toBeLessThanOrEqual(0);
      else expect(tracking).toBeLessThanOrEqual(0.1);
    }
  });

  it('loosens leading as type shrinks, so dense text stays readable', () => {
    const ratio = (key: keyof typeof tokens.type) =>
      tokens.type[key].lineHeight / tokens.type[key].fontSize;
    expect(ratio('hero')).toBeLessThan(ratio('body'));
    expect(ratio('title1')).toBeLessThan(ratio('body'));
  });

  it('keeps every control at or above the 44pt touch minimum', () => {
    expect(tokens.layout.touch).toBe(44);
    expect(tokens.layout.controlCompact).toBeGreaterThanOrEqual(tokens.layout.touch);
    expect(tokens.layout.control).toBeGreaterThanOrEqual(tokens.layout.controlCompact);
  });

  it('keeps ordinary motion under 300ms', () => {
    for (const duration of Object.values(tokens.motion.duration)) {
      expect(duration).toBeLessThan(300);
    }
  });
});
