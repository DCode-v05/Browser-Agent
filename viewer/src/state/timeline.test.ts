import { describe, expect, it } from 'vitest';

import type { Step } from './reducer';
import { buildRows, formatCount, formatDuration, formatElapsed, formatSize, markText } from './timeline';

function step(n: number, tool: string, summary: string, startedAt: number, extra: Partial<Step> = {}): Step {
  return { n, tool, label: `${summary}…`, startedAt, status: 'ok', ms: 50, chars: 100, summary, ...extra };
}

describe('rows', () => {
  it('one row per step, with the sentence of its result', () => {
    const rows = buildRows([step(1, 'browser_navigate', 'Opened example.com/login', 0), step(2, 'browser_click', 'Clicked "Sign in" (button)', 1)], 10);
    expect(rows.map((row) => row.kind === 'step' && row.text)).toEqual(['Opened example.com/login', 'Clicked "Sign in" (button)']);
  });

  it('a running step shows what the agent is doing', () => {
    const running: Step = { n: 3, tool: 'browser_click', label: 'Clicking "Create account"', startedAt: 2, status: 'running' };
    const [row] = buildRows([running], 10);
    expect(row).toMatchObject({ kind: 'step', text: 'Clicking "Create account"', count: 1 });
  });

  it('consecutive reads collapse into one row with a count and their total time', () => {
    const rows = buildRows(
      [
        step(1, 'browser_navigate', 'Opened example.com', 0),
        step(2, 'browser_snapshot', 'Read the page', 1, { ms: 3 }),
        step(3, 'browser_get_text', 'Read the page', 2, { ms: 2 }),
        step(4, 'browser_snapshot', 'Read the page', 3, { ms: 4 }),
        step(5, 'browser_click', 'Clicked "Next"', 4),
      ],
      10,
    );
    expect(rows).toHaveLength(3);
    expect(rows[1]).toMatchObject({ kind: 'step', text: 'Read the page', count: 3, ms: 9 });
    expect(rows[1].kind === 'step' && rows[1].steps.map((item) => item.n)).toEqual([2, 3, 4]);
  });

  it('a failed read is not folded into its neighbours', () => {
    const rows = buildRows(
      [step(1, 'browser_snapshot', 'Read the page', 0), step(2, 'browser_snapshot', 'Could not read the page: the page changed', 1, { status: 'failed' }), step(3, 'browser_snapshot', 'Read the page', 2)],
      10,
    );
    expect(rows).toHaveLength(3);
  });

  it('a gap of idle_divider_s or more becomes an idle divider', () => {
    const rows = buildRows([step(1, 'browser_click', 'Clicked "A"', 0, { ms: 1000 }), step(2, 'browser_click', 'Clicked "B"', 24)], 10);
    expect(rows.map((row) => row.kind)).toEqual(['step', 'idle', 'step']);
    expect(rows[1]).toMatchObject({ kind: 'idle', seconds: 23 });
  });

  it('a shorter gap does not', () => {
    const rows = buildRows([step(1, 'browser_click', 'Clicked "A"', 0), step(2, 'browser_click', 'Clicked "B"', 9)], 10);
    expect(rows.map((row) => row.kind)).toEqual(['step', 'step']);
  });

  it('an idle gap between two reads keeps them apart', () => {
    const rows = buildRows([step(1, 'browser_snapshot', 'Read the page', 0), step(2, 'browser_snapshot', 'Read the page', 60)], 10);
    expect(rows.map((row) => row.kind)).toEqual(['step', 'idle', 'step']);
  });

  it('every row has a key that stays the same as the list grows', () => {
    const first = buildRows([step(1, 'browser_click', 'Clicked "A"', 0)], 10);
    const second = buildRows([step(1, 'browser_click', 'Clicked "A"', 0), step(2, 'browser_click', 'Clicked "B"', 30)], 10);
    expect(second[0].key).toBe(first[0].key);
    expect(new Set(second.map((row) => row.key)).size).toBe(second.length);
  });

  it('a "nobody is answering" marker is placed among the steps by when it happened', () => {
    const rows = buildRows(
      [step(1, 'browser_click', 'Clicked "A"', 0), step(2, 'browser_click', 'Clicked "B"', 10)],
      10,
      [{ key: 'unanswered-1', count: 3, at: 5 }],
    );
    expect(rows.map((row) => row.kind)).toEqual(['step', 'unanswered', 'step']);
    expect(rows[1]).toMatchObject({ kind: 'unanswered', count: 3 });
  });

  it('a marker before any step comes first, and does not begin the idle count', () => {
    const rows = buildRows([step(1, 'browser_click', 'Clicked "A"', 20)], 10, [{ key: 'unanswered-1', count: 1, at: 0 }]);
    expect(rows.map((row) => row.kind)).toEqual(['unanswered', 'step']);
  });
});

describe('a step\'s mark (spec 18.10)', () => {
  it('is worded for checked, allowed and refused', () => {
    expect(markText({ kind: 'checked' })).toBe('checked');
    expect(markText({ kind: 'allowed' })).toBe('you allowed');
    expect(markText({ kind: 'refused', reason: 'the task did not ask for it' })).toBe('Refused: the task did not ask for it');
  });
});

describe('formats', () => {
  it.each([
    [0.4, 'under 1 ms'],
    [48, '48 ms'],
    [999, '999 ms'],
    [1200, '1.2 s'],
    [61_000, '61 s'],
  ])('duration %s ms reads as %s', (ms, text) => {
    expect(formatDuration(ms)).toBe(text);
  });

  it.each([
    [0, '0:00'],
    [42, '0:42'],
    [62, '1:02'],
    [3723, '1:02:03'],
  ])('%s seconds elapsed reads as %s', (seconds, text) => {
    expect(formatElapsed(seconds)).toBe(text);
  });

  it('counts are grouped by thousands', () => {
    expect(formatCount(9140)).toBe('9,140');
  });

  it.each([
    [512, '512 B'],
    [20480, '20 KB'],
    [5_242_880, '5.0 MB'],
  ])('%s bytes reads as %s', (bytes, text) => {
    expect(formatSize(bytes)).toBe(text);
  });
});
