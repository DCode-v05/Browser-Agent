import { describe, expect, it } from 'vitest';

import type { ServerEvent } from '../protocol';
import { initialState, reduce, type ViewerState } from './reducer';
import { describeState } from './view';

const T0 = 1_759_480_000;
const STALE_AFTER = 5;

const started: ServerEvent = {
  type: 'session_started',
  session: 'default',
  agent: 'Claude Code',
  backend: 'remote_headless',
  browser: 'Chromium 153',
  viewport: { width: 1280, height: 800 },
  ts: T0,
};

function after(...events: ServerEvent[]): ViewerState {
  const connected = reduce(initialState, { type: 'connection', status: 'connected' });
  return events.reduce((state, event) => reduce(state, { type: 'event', event }), connected);
}

const control = (state: Extract<ServerEvent, { type: 'control_changed' }>['state']): ServerEvent => ({ type: 'control_changed', state, since: T0 + 5 });

describe('what each state looks like (spec 9.3)', () => {
  it('no agent yet', () => {
    expect(describeState(after(), T0, STALE_AFTER)).toMatchObject({
      key: 'no_agent',
      status: 'Waiting for an agent to connect',
      tone: 'none',
      label: '',
      controls: [],
      urgency: 'polite',
    });
  });

  it('agent', () => {
    const state = after(started, { type: 'step_started', step: 1, tool: 'browser_click', label: 'Clicking "Create account"', ts: T0 + 1 });
    expect(describeState(state, T0 + 42, STALE_AFTER)).toMatchObject({
      key: 'agent',
      status: 'Agent is working',
      detail: 'Clicking "Create account"',
      tone: 'agent',
      label: 'Agent is working',
      controls: ['pause', 'take_over', 'stop'],
      urgency: 'polite',
      since: T0,
    });
  });

  it('agent, between steps, says what it did last', () => {
    const state = after(
      started,
      { type: 'step_started', step: 1, tool: 'browser_click', label: 'Clicking "Next"', ts: T0 + 1 },
      { type: 'step_finished', step: 1, ok: true, ms: 40, chars: 80, summary: 'Clicked "Next" (button)', url: 'https://example.com/' },
    );
    expect(describeState(state, T0 + 2, STALE_AFTER).detail).toBe('Clicked "Next" (button)');
  });

  it('waiting for approval', () => {
    expect(describeState(after(started, control('waiting_approval')), T0 + 6, STALE_AFTER)).toMatchObject({
      key: 'waiting_approval',
      status: 'Waiting for your approval',
      tone: 'waiting',
      label: 'Paused for approval',
      controls: ['stop'],
      urgency: 'assertive',
    });
  });

  it('person requested', () => {
    const state = after(started, { type: 'help_requested', id: 'h1', reason: 'sign in to github.com', kind: 'login', expires_in_s: 900, ts: T0 + 5 }, control('person_requested'));
    expect(describeState(state, T0 + 6, STALE_AFTER)).toMatchObject({
      key: 'person_requested',
      status: 'The agent asked for help',
      detail: 'sign in to github.com',
      tone: 'waiting',
      label: 'Agent asked for help',
      controls: ['take_over', 'could_not', 'stop'],
      urgency: 'assertive',
    });
  });

  it('person, after taking over unasked', () => {
    expect(describeState(after(started, control('person')), T0 + 6, STALE_AFTER)).toMatchObject({
      key: 'person',
      status: "You're in control",
      tone: 'person',
      label: "You're in control",
      controls: ['hand_back', 'stop'],
      urgency: 'assertive',
    });
  });

  it('person, answering a request for help', () => {
    const state = after(started, { type: 'help_requested', id: 'h1', reason: 'enter the code', kind: 'verification', expires_in_s: 900, ts: T0 + 5 }, control('person'));
    expect(describeState(state, T0 + 6, STALE_AFTER).controls).toEqual(['done', 'could_not', 'stop']);
  });

  it('paused', () => {
    expect(describeState(after(started, control('paused')), T0 + 6, STALE_AFTER)).toMatchObject({
      key: 'paused',
      status: 'Paused',
      tone: 'neutral',
      label: 'Paused',
      controls: ['resume', 'take_over', 'stop'],
      urgency: 'polite',
    });
  });

  it('blocked', () => {
    const state = after(started, { type: 'navigation_blocked', url: 'http://10.0.0.5/', reason: 'private address', ts: T0 + 3 });
    expect(describeState(state, T0 + 4, STALE_AFTER)).toMatchObject({
      key: 'blocked',
      status: 'Blocked: private address',
      tone: 'danger',
      label: 'Blocked',
      controls: ['take_over', 'stop'],
      urgency: 'assertive',
    });
  });

  it('ended', () => {
    const state = after(started, { type: 'session_ended', reason: 'person', ts: T0 + 60 });
    expect(describeState(state, T0 + 61, STALE_AFTER)).toMatchObject({
      key: 'ended',
      status: 'Session ended',
      detail: 'You stopped it.',
      tone: 'none',
      controls: [],
      urgency: 'polite',
      frame: 'ended',
    });
  });

  it('a refused link says what to do, offers no controls, and is not called a lost connection', () => {
    const state = reduce(after(started), { type: 'connection', status: 'refused' });
    expect(describeState(reduce(state, { type: 'frame', src: 'a.jpg', at: T0 + 1 }), T0 + 2, STALE_AFTER)).toMatchObject({
      key: 'refused',
      status: "This link can't open the session",
      detail: 'Open it again from where you started the session.',
      controls: [],
      urgency: 'assertive',
      frame: 'disconnected',
    });
  });

  it('a refused link with nothing shown yet has no picture to dim', () => {
    const state = reduce(initialState, { type: 'connection', status: 'refused' });
    expect(describeState(state, T0, STALE_AFTER)).toMatchObject({ key: 'refused', frame: 'empty', controls: [] });
  });

  it('disconnected hides the controls and says the picture is not live', () => {
    const state = reduce(after(started), { type: 'connection', status: 'reconnecting' });
    expect(describeState(state, T0 + 1, STALE_AFTER)).toMatchObject({
      key: 'disconnected',
      status: 'Connection lost. Reconnecting…',
      label: 'Not live',
      controls: [],
      urgency: 'assertive',
      frame: 'disconnected',
    });
  });

  it('a lost connection is shown even after the session ended', () => {
    const ended = after(started, { type: 'session_ended', reason: 'agent', ts: T0 + 60 });
    expect(describeState(reduce(ended, { type: 'connection', status: 'reconnecting' }), T0 + 61, STALE_AFTER).key).toBe('disconnected');
  });
});

describe('the live picture', () => {
  it('is connecting until the first picture arrives', () => {
    expect(describeState(after(started), T0 + 1, STALE_AFTER).frame).toBe('connecting');
  });

  it('is live while pictures keep coming', () => {
    const state = reduce(after(started), { type: 'frame', src: 'a.jpg', at: T0 + 1 });
    expect(describeState(state, T0 + 3, STALE_AFTER).frame).toBe('live');
  });

  it('is stale after stale_after_s without a picture, and that changes nothing else', () => {
    const state = reduce(after(started), { type: 'frame', src: 'a.jpg', at: T0 + 1 });
    const view = describeState(state, T0 + 7, STALE_AFTER);
    expect(view.frame).toBe('stale');
    expect(view.key).toBe('agent');
    expect(view.controls).toEqual(['pause', 'take_over', 'stop']);
  });

  it('is not called stale while paused or while a person drives', () => {
    const paused = reduce(after(started, control('paused')), { type: 'frame', src: 'a.jpg', at: T0 + 1 });
    expect(describeState(paused, T0 + 60, STALE_AFTER).frame).toBe('paused');
    const person = reduce(after(started, control('person')), { type: 'frame', src: 'a.jpg', at: T0 + 1 });
    expect(describeState(person, T0 + 60, STALE_AFTER).frame).toBe('person');
  });
});

describe('a take-over Chrome session', () => {
  it('has no live picture, because the person is looking at their own browser', () => {
    const state = after({ ...started, backend: 'takeover_chrome' } as ServerEvent);
    expect(describeState(state, T0 + 1, STALE_AFTER).frame).toBe('own_browser');
  });
});
