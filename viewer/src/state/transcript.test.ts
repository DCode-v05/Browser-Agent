import { describe, expect, it } from 'vitest';

import type { ChatMessage, Step } from './reducer';
import { transcript } from './transcript';

const said = (id: number, role: ChatMessage['role'], at: number, text = `message ${id}`): ChatMessage => ({ id, role, text, failed: false, at });
const step = (n: number, startedAt: number): Step => ({ n, tool: 'browser_click', label: `step ${n}`, startedAt, status: 'ok' });

const shape = (items: ReturnType<typeof transcript>) => items.map((item) => (item.kind === 'steps' ? item.steps.map((one) => one.n) : `${item.kind} ${item.text}`));

describe('the conversation', () => {
  it('is empty before anything was said or done', () => {
    expect(transcript([], [])).toEqual([]);
  });

  it('puts the steps between the task that led to them and the answer that followed', () => {
    const items = transcript([said(1, 'person', 10, 'Check in'), said(2, 'agent', 20, 'You have seat 14A')], [step(1, 11), step(2, 12), step(3, 15)]);
    expect(shape(items)).toEqual(['person Check in', [1, 2, 3], 'agent You have seat 14A']);
  });

  it('starts a new group of steps after each thing that was said', () => {
    const items = transcript(
      [said(1, 'person', 10), said(2, 'agent', 13, 'I will read the page first'), said(3, 'agent', 20), said(4, 'person', 30)],
      [step(1, 11), step(2, 12), step(3, 14), step(4, 31)],
    );
    expect(shape(items)).toEqual(['person message 1', [1, 2], 'agent I will read the page first', [3], 'agent message 3', 'person message 4', [4]]);
  });

  it('at the same moment, a task comes before its steps and an answer after them', () => {
    expect(shape(transcript([said(1, 'person', 10), said(2, 'agent', 12)], [step(1, 10), step(2, 12)]))).toEqual(['person message 1', [1, 2], 'agent message 2']);
  });

  it('keeps steps that were taken before anyone said anything', () => {
    expect(shape(transcript([said(1, 'person', 10)], [step(1, 5)]))).toEqual([[1], 'person message 1']);
  });

  it('marks an answer that says the task failed', () => {
    const failed: ChatMessage = { ...said(1, 'agent', 10, 'The model could not answer'), failed: true };
    expect(transcript([failed], [])).toEqual([{ kind: 'agent', key: 'm1', text: 'The model could not answer', failed: true }]);
  });
});
