import { existsSync, readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

// Tests run from the viewer folder. The test runner does not hand CSS files to imports.
const css = readFileSync('src/tokens.css', 'utf8');

/** Every token a block sets, with its value as written. */
function values(selector: string): Record<string, string> {
  const start = css.indexOf(selector + ' {');
  expect(start, `block ${selector}`).toBeGreaterThanOrEqual(0);
  const body = css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start));
  const tokens: Record<string, string> = {};
  for (const match of body.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) tokens[match[1]] = match[2].trim();
  return tokens;
}

/** The tokens of a block that are one opaque colour. */
function block(selector: string): Record<string, string> {
  return Object.fromEntries(Object.entries(values(selector)).filter(([, value]) => /^#[0-9A-Fa-f]{6}$/.test(value)));
}

function luminance(hex: string): number {
  const channel = (index: number) => {
    const value = parseInt(hex.slice(index, index + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(one: string, other: string): number {
  const [light, dark] = [luminance(one), luminance(other)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

const light = block(':root');
const dark = { ...light, ...block(':root[data-theme="dark"]') };
const darkBySystem = { ...light, ...block(':root:not([data-theme="light"])') };

const ACCENTS = ['agent', 'person', 'waiting', 'danger', 'success'];
const SURFACES = ['--bg', '--surface', '--surface-2', '--surface-3'];

// [foreground, background]: text needs 4.5:1.
const TEXT_PAIRS: [string, string][] = [
  ...SURFACES.flatMap((surface): [string, string][] => [
    ['--text', surface],
    ['--text-muted', surface],
  ]),
  ['--on-ink', '--ink'], // the label of the main action
  ...ACCENTS.flatMap((name): [string, string][] => [
    [`--${name}`, `--${name}-tint`],
    [`--${name}`, '--surface'],
    [`--${name}`, '--bg'],
    [`--${name}`, '--surface-2'], // a failed or running row under the pointer
    ['--surface', `--${name}`], // the label of a filled button
  ]),
];

// Edges of controls and the focus ring need 3:1.
const CONTROL_PAIRS: [string, string][] = [
  ['--border-strong', '--surface'],
  ['--border-strong', '--bg'],
  ['--border-strong', '--surface-2'],
  ...SURFACES.map((surface): [string, string] => ['--focus', surface]),
];

describe.each([
  ['light', light],
  ['dark', dark],
])('%s theme', (_name, tokens) => {
  it.each(TEXT_PAIRS)('%s on %s is readable as text', (foreground, background) => {
    expect(contrast(tokens[foreground], tokens[background])).toBeGreaterThanOrEqual(4.5);
  });

  it.each(CONTROL_PAIRS)('%s on %s is visible as a control edge', (foreground, background) => {
    expect(contrast(tokens[foreground], tokens[background])).toBeGreaterThanOrEqual(3);
  });
});

it('the lowest text pair is the success colour on the warm surface in the light theme, at 4.91:1', () => {
  const ratios = TEXT_PAIRS.filter(([foreground]) => foreground !== '--surface').map(
    ([foreground, background]) => contrast(light[foreground], light[background]),
  );
  expect(Math.min(...ratios)).toBeCloseTo(contrast(light['--success'], light['--surface-2']), 5);
  expect(contrast(light['--success'], light['--surface-2'])).toBeCloseTo(4.91, 1);
});

it('the dark palette is the same whether the system or the person chose it', () => {
  expect(values(':root:not([data-theme="light"])')).toEqual(values(':root[data-theme="dark"]'));
  expect(darkBySystem).toEqual(dark);
});

it('every colour, see-through colour, gradient and shadow has a dark value', () => {
  const coloured = Object.entries(values(':root'))
    .filter(([, value]) => /#[0-9A-Fa-f]{3,8}\b|\brgb\(/.test(value))
    .map(([name]) => name);
  expect(coloured.length).toBeGreaterThan(20);
  expect(Object.keys(values(':root[data-theme="dark"]')).sort()).toEqual(coloured.sort());
});

describe('the typeface', () => {
  it('is Hanken Grotesk first, then the system font', () => {
    expect(values(':root')['--font-ui']).toMatch(/^"Hanken Grotesk", system-ui, /);
  });

  it('ships with the viewer: nothing is fetched from another site', () => {
    const files = [...css.matchAll(/url\(['"]?([^'")]+)['"]?\)/g)].map((match) => match[1]);
    expect(files).toEqual(['./fonts/hanken-grotesk-latin-ext.woff2', './fonts/hanken-grotesk-latin.woff2']);
    for (const file of files) expect(existsSync(`src/${file}`), file).toBe(true);
    expect(existsSync('src/fonts/OFL.txt'), 'the licence travels with the font').toBe(true);
  });
});
