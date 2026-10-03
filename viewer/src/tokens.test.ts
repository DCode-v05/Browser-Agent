import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

// Tests run from the viewer folder. The test runner does not hand CSS files to imports.
const css = readFileSync('src/tokens.css', 'utf8');

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector + ' {');
  expect(start, `block ${selector}`).toBeGreaterThanOrEqual(0);
  const body = css.slice(css.indexOf('{', start) + 1, css.indexOf('}', start));
  const tokens: Record<string, string> = {};
  for (const match of body.matchAll(/(--[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6})\s*;/g)) tokens[match[1]] = match[2];
  return tokens;
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

// [foreground, background]: text needs 4.5:1.
const TEXT_PAIRS: [string, string][] = [
  ['--text', '--bg'],
  ['--text', '--surface'],
  ['--text', '--surface-2'],
  ['--text-muted', '--bg'],
  ['--text-muted', '--surface'],
  ['--text-muted', '--surface-2'],
  ...ACCENTS.flatMap((name): [string, string][] => [
    [`--${name}`, `--${name}-tint`],
    [`--${name}`, '--surface'],
    [`--${name}`, '--bg'],
    ['--surface', `--${name}`], // the label of a filled button
  ]),
];

// Edges of controls and the focus ring need 3:1.
const CONTROL_PAIRS: [string, string][] = [
  ['--border-strong', '--surface'],
  ['--border-strong', '--bg'],
  ['--focus', '--surface'],
  ['--focus', '--bg'],
  ['--focus', '--surface-2'],
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

it('the lowest text pair is the person colour on its tint in the light theme, at 4.95:1', () => {
  const ratios = TEXT_PAIRS.filter(([foreground]) => foreground !== '--surface').map(
    ([foreground, background]) => contrast(light[foreground], light[background]),
  );
  expect(Math.min(...ratios)).toBeCloseTo(contrast(light['--person'], light['--person-tint']), 5);
  expect(contrast(light['--person'], light['--person-tint'])).toBeCloseTo(4.95, 1);
});

it('the dark palette is the same whether the system or the person chose it', () => {
  expect(darkBySystem).toEqual(dark);
});

it('every colour has a dark value', () => {
  const colours = Object.keys(block(':root'));
  expect(Object.keys(block(':root[data-theme="dark"]')).sort()).toEqual(colours.sort());
});
