import { describe, expect, it } from 'vitest';

import { DemoConnection, type RecordedSession } from '../connection/demo';
import { initialState, reduce, type ViewerState } from '../state/reducer';
import { buildRows } from '../state/timeline';
import { describeState, type FrameState, type StateKey } from '../state/view';
import { SIGNUP_SESSION, STATES } from './sessions';

const STALE_AFTER = 5;

function settle(session: RecordedSession): { state: ViewerState; now: number } {
  let state = initialState;
  const connection = new DemoConnection(session, { pace: 0, startAt: 1000, realNow: () => 0, heartbeatMs: 2000 });
  connection.start({
    onEvent: (event, picture) => (state = reduce(state, { type: 'event', event, picture })),
    onFrame: (src, at) => (state = reduce(state, { type: 'frame', src, at })),
    onStatus: (status) => (state = reduce(state, { type: 'connection', status })),
  });
  const now = connection.now();
  connection.close();
  return { state, now };
}

const EXPECTED: Record<string, { key: StateKey; frame: FrameState }> = {
  no_agent: { key: 'no_agent', frame: 'empty' },
  empty: { key: 'agent', frame: 'connecting' },
  agent: { key: 'agent', frame: 'live' },
  waiting_approval: { key: 'waiting_approval', frame: 'live' },
  person_requested: { key: 'person_requested', frame: 'live' },
  person: { key: 'person', frame: 'person' },
  person_unasked: { key: 'person', frame: 'person' },
  paused: { key: 'paused', frame: 'paused' },
  blocked: { key: 'blocked', frame: 'live' },
  dialog: { key: 'agent', frame: 'live' },
  denied: { key: 'agent', frame: 'live' },
  ended: { key: 'ended', frame: 'ended' },
  disconnected: { key: 'disconnected', frame: 'disconnected' },
  stale: { key: 'agent', frame: 'stale' },
  own_browser: { key: 'agent', frame: 'own_browser' },
};

describe('the recording for each state', () => {
  it('there is one for every state the viewer can show', () => {
    expect(Object.keys(STATES).sort()).toEqual(Object.keys(EXPECTED).sort());
  });

  it.each(Object.entries(EXPECTED))('%s stops in that state', (name, expected) => {
    const { state, now } = settle(STATES[name]);
    const view = describeState(state, now, STALE_AFTER);
    expect({ key: view.key, frame: view.frame }).toEqual(expected);
  });

  it('person answers a request for help; person_unasked took over without one', () => {
    expect(settle(STATES.person).state.help).not.toBeNull();
    expect(settle(STATES.person_unasked).state.help).toBeNull();
  });

  it('waiting_approval and dialog have their cards pending', () => {
    expect(settle(STATES.waiting_approval).state.approval?.summary).toBe('Upload cv.pdf to example.com');
    expect(settle(STATES.dialog).state.dialog?.kind).toBe('confirm');
  });

  it('denied leaves a failed step behind', () => {
    const { state } = settle(STATES.denied);
    expect(state.steps.find((step) => step.n === 6)).toMatchObject({ status: 'failed', summary: 'Could not upload cv.pdf: a person did not approve it' });
  });
});

describe('the full run', () => {
  const { state } = settle({ ...SIGNUP_SESSION, auto: { approval: 'allow', help: 'done' } });

  it('ends because the agent closed it, after sixteen steps', () => {
    expect(state.ended?.reason).toBe('agent');
    expect(state.steps.map((step) => step.n)).toEqual(Array.from({ length: 16 }, (_, index) => index + 1));
    expect(state.steps.every((step) => step.status !== 'running')).toBe(true);
  });

  it('shows every kind of timeline row: collapsed reads, a failure, an idle gap', () => {
    const rows = buildRows(state.steps, 10);
    expect(rows.some((row) => row.kind === 'step' && row.count === 2)).toBe(true);
    expect(rows.some((row) => row.kind === 'step' && row.status === 'failed')).toBe(true);
    expect(rows.some((row) => row.kind === 'idle')).toBe(true);
  });

  it('never carries typed text', () => {
    const everything = JSON.stringify(SIGNUP_SESSION.beats);
    expect(everything).not.toContain('Ada Lovelace');
    expect(everything).toContain('Typed 12 characters');
  });

  it('keeps every sentence under 60 characters', () => {
    for (const step of state.steps) {
      expect((step.summary ?? '').length, step.summary).toBeLessThanOrEqual(60);
      expect(step.label.length, step.label).toBeLessThanOrEqual(60);
    }
  });

  it('every acting step has a picture', () => {
    const acted = state.steps.filter((step) => ['browser_navigate', 'browser_type', 'browser_click'].includes(step.tool) && step.status === 'ok');
    expect(acted.every((step) => Boolean(step.picture))).toBe(true);
  });
});
