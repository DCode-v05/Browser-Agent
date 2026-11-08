import { readdirSync, readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

const files = readdirSync('src/styles').filter((name) => name.endsWith('.css'));

function rules(name: string): string[] {
  return (
    readFileSync(`src/styles/${name}`, 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .filter((line) => !line.trim().startsWith('@media'))
  );
}

describe.each(files)('%s', (name) => {
  const lines = rules(name);

  it('has no colour written out', () => {
    expect(lines.filter((line) => /#[0-9a-fA-F]{3,8}\b|\b(rgb|hsl)a?\(/.test(line))).toEqual([]);
  });

  it('has no size in pixels written out', () => {
    expect(lines.filter((line) => /\d+px\b/.test(line))).toEqual([]);
  });

  it('has no duration written out', () => {
    expect(lines.filter((line) => /\b\d*\.?\d+m?s\b/.test(line))).toEqual([]);
  });

  it('names no font', () => {
    expect(lines.filter((line) => /font(-family)?:/.test(line) && !/var\(--font-|inherit/.test(line))).toEqual([]);
  });
});

it('there are stylesheets to check', () => {
  expect(files.sort()).toEqual(['app.css', 'base.css', 'settings.css']);
});
