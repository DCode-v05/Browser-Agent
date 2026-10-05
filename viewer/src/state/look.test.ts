import { describe, expect, it, vi } from 'vitest';

import type { ServerEvent } from '../protocol';
import { LOOK, lookOf, tellPanel, type Look } from './look';
import { initialState, reduce, type ViewerState } from './reducer';
import { describeState } from './view';

const T0 = 1_759_480_000;
const BUTTON = { x: 100, y: 200, w: 80, h: 40 };

const started: ServerEvent = {
  type: 'session_started',
  session: 'default',
  agent: 'Reference agent',
  backend: 'remote_headless',
  browser: 'Chromium 153',
  viewport: { width: 1280, height: 800 },
  chat: true,
  on_screen: true,
  ts: T0,
};
const working: ServerEvent = { type: 'task_changed', working: true, ts: T0 };
const clicking: ServerEvent = { type: 'step_started', step: 1, tool: 'browser_click', label: 'Clicking "Find booking" (button)', target: BUTTON, ts: T0 };
const clicked: ServerEvent = { type: 'step_finished', step: 1, ok: true, ms: 40, chars: 60, summary: 'Clicked "Find booking" (button)', url: 'https://example.com/' };

function look(events: ServerEvent[], showPointer = true): Look {
  let state: ViewerState = reduce(initialState, { type: 'connection', status: 'connected' });
  for (const event of events) state = reduce(state, { type: 'event', event });
  return lookOf(state, describeState(state, T0 + 1, 5), showPointer);
}

describe('what a page shows about who is driving', () => {
  it('nothing before a session, and nothing while the agent waits for a task', () => {
    expect(look([])).toMatchObject({ type: LOOK, tone: 'none', working: false, label: '' });
    expect(look([started]).tone).toBe('none');
    expect(look([started, working, { type: 'task_changed', working: false, ts: T0 }]).tone).toBe('none');
  });

  it('while the agent works: its colour, what it is doing, and the element it is acting on', () => {
    expect(look([started, working, clicking])).toEqual({
      type: LOOK,
      tone: 'agent',
      working: true,
      label: 'Agent is working',
      detail: 'Clicking "Find booking" (button)',
      target: BUTTON,
      pointer: { x: 140, y: 220 },
      click: null,
    });
  });

  it('after a click: the outline goes, the pointer stays there, and the click is marked once by its step', () => {
    expect(look([started, working, clicking, clicked])).toMatchObject({ target: null, pointer: { x: 140, y: 220 }, click: 1 });
  });

  it('a step that is not a click marks none', () => {
    const typing: ServerEvent = { ...clicking, tool: 'browser_type', label: 'Typing 6 characters into "Booking reference"' };
    expect(look([started, working, typing, clicked]).click).toBeNull();
  });

  it('with the agent\'s pointer switched off, only the edge and the label are shown', () => {
    expect(look([started, working, clicking], false)).toMatchObject({ tone: 'agent', target: null, pointer: null, click: null });
  });

  it('a person in control: their colour and words, and no pointer of the agent', () => {
    const taken = look([started, working, clicking, clicked, { type: 'control_changed', state: 'person', since: T0 }]);
    expect(taken).toMatchObject({ tone: 'person', working: false, label: "You're in control", detail: '', pointer: null });
  });

  it('paused: said in words, and still', () => {
    const paused = look([started, working, clicking, { type: 'control_changed', state: 'paused', since: T0 }]);
    expect(paused).toMatchObject({ tone: 'neutral', working: false, label: 'Paused' });
  });

  it('nothing once the session has ended', () => {
    expect(look([started, working, clicking, { type: 'session_ended', reason: 'person', ts: T0 }]).tone).toBe('none');
  });
});

describe('telling the side panel', () => {
  it('sends the look with the colours of its tone, read from the viewer\'s own theme', () => {
    const root = document.createElement('div');
    root.style.setProperty('--agent', '#6E3B83');
    root.style.setProperty('--surface', '#FFFFFF');
    document.body.append(root);
    const panel = { postMessage: vi.fn() };
    const shown = look([started, working, clicking]);
    tellPanel(shown, panel, root);
    expect(panel.postMessage).toHaveBeenCalledWith({ ...shown, colour: '#6E3B83', onColour: '#FFFFFF' }, '*');
    root.remove();
  });
});
