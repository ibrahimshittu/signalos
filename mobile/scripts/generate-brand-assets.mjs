/**
 * Regenerates the SignalOS launch assets from a single source of truth.
 *
 * The mark is defined once here, in the same 32-unit grid the in-app
 * `BrandMark` uses, so the icon, the splash, and the header lockup can never
 * drift apart. Run after any change to the mark or the accent:
 *
 *   node scripts/generate-brand-assets.mjs
 *
 * Rendering is delegated to Python's Pillow because it is the only rasteriser
 * present on a stock macOS toolchain.
 */
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

/** Must match tokens.color.accent.base and tokens.color.bg.canvas. */
const ACCENT = '#1A4E8A';
const ON_ACCENT = '#FFFFFF';
const CANVAS = '#F4F5F7';

/** The mark, on a 32x32 grid. Mirrors components/ui/Brand.tsx exactly. */
const GRID = 32;
const TILE_RADIUS = 9;
const STROKE = 2.75;
const PATH = [
  [7.5, 21.5],
  [13, 15.5],
  [17, 19],
  [24.5, 10.5],
];

const script = `
import sys
from PIL import Image, ImageDraw

GRID = ${GRID}
SUPERSAMPLE = 4
ACCENT = "${ACCENT}"
ON_ACCENT = "${ON_ACCENT}"
PATH = ${JSON.stringify(PATH)}
STROKE = ${STROKE}
TILE_RADIUS = ${TILE_RADIUS}


def draw_mark(size, *, tile, inset_ratio):
    """Render the mark at \`size\` px, optionally on a rounded accent tile."""
    scale = size * SUPERSAMPLE / GRID
    canvas = Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    if tile:
        draw.rounded_rectangle(
            [0, 0, size * SUPERSAMPLE - 1, size * SUPERSAMPLE - 1],
            radius=TILE_RADIUS * scale,
            fill=ACCENT,
        )

    # Shrink the path toward the centre when the artwork needs a safe zone.
    centre = GRID / 2
    points = [
        ((x - centre) * inset_ratio + centre) * scale for point in PATH for x in point
    ]
    points = list(zip(points[0::2], points[1::2]))

    width = int(round(STROKE * inset_ratio * scale))
    draw.line(points, fill=ON_ACCENT, width=width, joint="curve")
    # Pillow has no round line cap; the end discs supply one.
    for x, y in (points[0], points[-1]):
        radius = width / 2
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=ON_ACCENT)

    return canvas.resize((size, size), Image.LANCZOS)


def flatten(image, background):
    solid = Image.new("RGBA", image.size, background)
    return Image.alpha_composite(solid, image).convert("RGB")


root = sys.argv[1]

# App icon: opaque, full-bleed. iOS applies its own mask, so the artwork must
# not round its own corners or it shows a halo inside the system mask.
icon = draw_mark(1024, tile=False, inset_ratio=1.0)
flatten(icon, ACCENT).save(root + "/assets/images/signalos-icon.png")

# Android adaptive foreground: transparent, inside the 66% safe zone. The
# background colour is set in app.json to the accent, so the path is white.
draw_mark(1024, tile=False, inset_ratio=0.58).save(
    root + "/assets/images/signalos-adaptive-foreground.png"
)

# Splash: the tile itself, transparent outside, sitting on the canvas colour.
draw_mark(512, tile=True, inset_ratio=1.0).save(root + "/assets/images/signalos-splash.png")
print("icon, adaptive foreground, and splash written")
`;

execFileSync('python3', ['-c', script, root], { stdio: 'inherit' });

/* ------------------------------------------------------------ vector source */

const points = PATH.map(([x, y]) => `${x} ${y}`);
const path = `M${points[0]} L${points.slice(1).join(' L')}`;
const stroke = `fill="none" stroke="${ON_ACCENT}" stroke-linecap="round" stroke-linejoin="round" stroke-width="${STROKE}"`;

const files = {
  'assets/brand/signalos-mark.svg': `<svg xmlns="http://www.w3.org/2000/svg" width="${GRID * 8}" height="${GRID * 8}" viewBox="0 0 ${GRID} ${GRID}" role="img" aria-labelledby="title">
  <title id="title">SignalOS</title>
  <rect width="${GRID}" height="${GRID}" rx="${TILE_RADIUS}" fill="${ACCENT}"/>
  <path d="${path}" ${stroke}/>
</svg>
`,
  'assets/brand/signalos-icon.svg': `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 ${GRID} ${GRID}" role="img" aria-labelledby="title">
  <title id="title">SignalOS app icon</title>
  <rect width="${GRID}" height="${GRID}" fill="${ACCENT}"/>
  <path d="${path}" ${stroke}/>
</svg>
`,
  'assets/brand/signalos-splash.svg': `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 ${GRID} ${GRID}" role="img" aria-labelledby="title">
  <title id="title">SignalOS splash</title>
  <rect width="${GRID}" height="${GRID}" rx="${TILE_RADIUS}" fill="${ACCENT}"/>
  <path d="${path}" ${stroke}/>
</svg>
`,
  'assets/brand/signalos-lockup.svg': `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="160" viewBox="0 0 144 32" role="img" aria-labelledby="title">
  <title id="title">SignalOS</title>
  <rect width="${GRID}" height="${GRID}" rx="${TILE_RADIUS}" fill="${ACCENT}"/>
  <path d="${path}" ${stroke}/>
  <text x="42" y="22" font-family="-apple-system, SF Pro Text, Helvetica, Arial, sans-serif" font-size="18" font-weight="600" letter-spacing="-0.2" fill="#15181C">SignalOS</text>
</svg>
`,
};

const { writeFileSync } = await import('node:fs');
for (const [file, contents] of Object.entries(files)) {
  writeFileSync(join(root, file), contents);
}
console.log(`${Object.keys(files).length} vector sources written`);
console.log(`splash background should stay ${CANVAS}`);
