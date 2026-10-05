import { describe, expect, it } from 'vitest';

import type { ServerEvent } from '../protocol';
import { initialState, reduce, unseenNotices, type ViewerState } from './reducer';

const T0 = 1_759_480_000;

const started: ServerEvent = {
  type: 'session_started',
  session: 'default',
  agent: 'Claude Code',
  backend: 'remote_headless',
  browser: 'Chromium 153',
  viewport: { width: 1280, height: 800 },
  ts: T0,
};

function play(events: ServerEvent[], from: ViewerState = initialState): ViewerState {
  return events.reduce((state, event) => reduce(state, { type: 'event', event }), from);
}

function stepStarted(step: number, tool: string, label: string, at = T0 + step): ServerEvent {
  return { type: 'step_started', step, tool, label, ts: at };
}

function stepFinished(step: number, summary: string, extra: Partial<Extract<ServerEvent, { type: 'step_finished' }>> = {}): ServerEvent {
  return { type: 'step_finished', step, ok: true, ms: 48, chars: 96, summary, url: 'https://example.com/signup', ...extra };
}

describe('session', () => {
  it('starts with no agent', () => {
    expect(initialState.session).toBeNull();
    expect(initialState.control).toBe('none');
  });

  it('a session start puts the agent in control', () => {
    const state = play([started]);
    expect(state.session).toEqual({
      id: 'default',
      agent: 'Claude Code',
      backend: 'remote_headless',
      browser: 'Chromium 153',
      viewport: { width: 1280, height: 800 },
      onScreen: false,
      startedAt: T0,
    });
    expect(state.control).toBe('agent');
    expect(state.controlSince).toBe(T0);
  });

  it("a browser that is a window on the person's own screen is known as that", () => {
    expect(play([{ ...started, on_screen: true }]).session?.onScreen).toBe(true);
  });

  it('a new session forgets the previous one', () => {
    const first = play([started, stepStarted(1, 'browser_navigate', 'Opening example.com'), stepFinished(1, 'Opened example.com')]);
    const second = play([{ ...started, session: 'second', ts: T0 + 100 }], first);
    expect(second.steps).toEqual([]);
    expect(second.session?.id).toBe('second');
    expect(second.chars).toBe(0);
  });

  it('the end of a session is kept with its reason', () => {
    const state = play([started, { type: 'session_ended', reason: 'person', ts: T0 + 60 }]);
    expect(state.control).toBe('ended');
    expect(state.ended).toEqual({ reason: 'person', detail: undefined, at: T0 + 60 });
  });
});

describe('control', () => {
  it.each(['waiting_approval', 'person_requested', 'person', 'paused', 'agent'] as const)('follows control_changed to %s', (control) => {
    const state = play([started, { type: 'control_changed', state: control, since: T0 + 5 }]);
    expect(state.control).toBe(control);
    expect(state.controlSince).toBe(T0 + 5);
  });
});

describe('steps', () => {
  it('a started step is running and carries where the agent is about to act', () => {
    const state = play([started, { ...stepStarted(12, 'browser_click', 'Clicking "Create account"'), target: { x: 412, y: 388, w: 140, h: 36 } } as ServerEvent]);
    expect(state.steps).toEqual([
      { n: 12, tool: 'browser_click', label: 'Clicking "Create account"', target: { x: 412, y: 388, w: 140, h: 36 }, startedAt: T0 + 12, status: 'running' },
    ]);
  });

  it('a finished step keeps its result, the address and the picture that came with it', () => {
    let state = play([started, stepStarted(1, 'browser_navigate', 'Opening example.com/signup')]);
    state = reduce(state, { type: 'event', event: stepFinished(1, 'Opened example.com/signup', { ms: 120, chars: 640 }), picture: 'frame-1.jpg' });
    expect(state.steps[0]).toMatchObject({ status: 'ok', ms: 120, chars: 640, summary: 'Opened example.com/signup', picture: 'frame-1.jpg' });
    expect(state.url).toBe('https://example.com/signup');
    expect(state.chars).toBe(640);
  });

  it('a failed step is marked failed', () => {
    const state = play([started, stepStarted(3, 'browser_click', 'Clicking "Pay"'), stepFinished(3, 'Could not click "Pay": the element is covered by a dialog', { ok: false })]);
    expect(state.steps[0].status).toBe('failed');
  });

  it('characters returned to the agent add up', () => {
    const state = play([
      started,
      stepStarted(1, 'browser_navigate', 'Opening a'),
      stepFinished(1, 'Opened a', { chars: 600 }),
      stepStarted(2, 'browser_snapshot', 'Reading the page'),
      stepFinished(2, 'Read the page', { chars: 9000 }),
    ]);
    expect(state.chars).toBe(9600);
  });

  it('a result for a step that was never started is ignored', () => {
    const state = play([started, stepFinished(9, 'Read the page')]);
    expect(state.steps).toEqual([]);
  });

  it('a typing step carries a count, never text', () => {
    const state = play([started, stepStarted(2, 'browser_type', 'Typing 17 characters into "Email"'), stepFinished(2, 'Typed 17 characters into "Email"')]);
    expect(JSON.stringify(state.steps)).not.toMatch(/@/);
    expect(state.steps[0].summary).toBe('Typed 17 characters into "Email"');
  });
});

describe('tabs and address', () => {
  it('the address follows the active tab', () => {
    const state = play([
      started,
      {
        type: 'tab_changed',
        tabs: [
          { id: 't1', title: 'Sign up', url: 'https://example.com/signup', active: false },
          { id: 't2', title: 'Docs', url: 'https://example.com/docs', active: true },
        ],
      },
    ]);
    expect(state.tabs).toHaveLength(2);
    expect(state.url).toBe('https://example.com/docs');
  });
});

describe('approvals', () => {
  const requested: ServerEvent = { type: 'approval_requested', id: 'a7', tool: 'browser_upload_file', summary: 'Upload cv.pdf to example.com', site: 'example.com', expires_in_s: 180, ts: T0 + 20 };

  it('a request is pending until it is closed', () => {
    const state = play([started, requested]);
    expect(state.approval).toEqual({ id: 'a7', tool: 'browser_upload_file', summary: 'Upload cv.pdf to example.com', site: 'example.com', requestedAt: T0 + 20, expiresAt: T0 + 200 });
  });

  it.each(['allowed', 'allowed_site', 'denied', 'expired'] as const)('closing as %s clears it and records the outcome', (outcome) => {
    const state = play([started, requested, { type: 'approval_closed', id: 'a7', outcome }]);
    expect(state.approval).toBeNull();
    expect(state.notices.at(-1)).toMatchObject({ kind: 'approval', outcome, summary: 'Upload cv.pdf to example.com' });
  });

  it('closing a different request leaves the pending one', () => {
    const state = play([started, requested, { type: 'approval_closed', id: 'other', outcome: 'denied' }]);
    expect(state.approval?.id).toBe('a7');
  });

  it('an approval denied because nobody was watching is kept as a notice', () => {
    const state = play([started, requested, { type: 'approval_closed', id: 'a7', outcome: 'unwatched' }]);
    expect(state.notices.at(-1)).toMatchObject({ kind: 'approval', outcome: 'unwatched' });
  });
});

describe('help requests and dialogs', () => {
  const help: ServerEvent = { type: 'help_requested', id: 'h1', reason: 'sign in to github.com', kind: 'login', expires_in_s: 900, ts: T0 + 30 };
  const dialog: ServerEvent = { type: 'dialog_opened', id: 'd1', kind: 'confirm', text: 'Proceed?', expires_in_s: 120, ts: T0 + 40 };

  it('a help request is pending until it is closed', () => {
    const open = play([started, help]);
    expect(open.help).toEqual({ id: 'h1', reason: 'sign in to github.com', kind: 'login', requestedAt: T0 + 30, expiresAt: T0 + 930 });
    const closed = play([{ type: 'help_closed', id: 'h1', outcome: 'done' }], open);
    expect(closed.help).toBeNull();
    expect(closed.notices.at(-1)).toMatchObject({ kind: 'help', outcome: 'done' });
  });

  it('a page dialog is shown until it is answered', () => {
    const open = play([started, dialog]);
    expect(open.dialog).toEqual({ id: 'd1', kind: 'confirm', text: 'Proceed?', expiresAt: T0 + 160 });
    expect(play([{ type: 'dialog_closed', id: 'd1', outcome: 'accepted' }], open).dialog).toBeNull();
  });
});

describe('blocked pages, downloads, settings', () => {
  it('a blocked navigation stays until the agent starts another step', () => {
    const blocked = play([started, { type: 'navigation_blocked', url: 'http://10.0.0.5/', reason: 'private address', ts: T0 + 3 }]);
    expect(blocked.blocked).toEqual({ url: 'http://10.0.0.5/', reason: 'private address', at: T0 + 3 });
    expect(play([stepStarted(4, 'browser_snapshot', 'Reading the page')], blocked).blocked).toBeNull();
  });

  it('a download is listed and noticed', () => {
    const state = play([started, { type: 'download_saved', name: 'report.pdf', size: 20480, ts: T0 + 9 }]);
    expect(state.downloads).toEqual([{ name: 'report.pdf', size: 20480 }]);
    expect(state.notices.at(-1)).toMatchObject({ kind: 'download', name: 'report.pdf' });
  });

  it('a settings change bumps the settings version so the screen reads them again', () => {
    const state = play([started, { type: 'settings_changed', changes: { ask_before: 'every_action' } }]);
    expect(state.settingsVersion).toBe(initialState.settingsVersion + 1);
  });
});

describe('pictures and connection', () => {
  it('a finished step that came with no picture has none, whatever the live picture shows', () => {
    let state = play([started, stepStarted(1, 'browser_navigate', 'Opening example.com/signup')]);
    state = reduce(state, { type: 'frame', src: 'live.jpg', at: T0 + 1 });
    state = play([stepFinished(1, 'Opened example.com/signup')], state);
    expect(state.steps[0].picture).toBeUndefined();
  });

  it('the newest picture replaces the last', () => {
    let state = reduce(initialState, { type: 'frame', src: 'a.jpg', at: 1 });
    state = reduce(state, { type: 'frame', src: 'b.jpg', at: 2 });
    expect(state.frame).toEqual({ src: 'b.jpg', at: 2 });
  });

  it('a picture the service confirms as current keeps its image and gets a new time', () => {
    let state = reduce(initialState, { type: 'frame', src: 'a.jpg', at: 1 });
    state = reduce(state, { type: 'event', event: { type: 'picture_current', ts: 9 } });
    expect(state.frame).toEqual({ src: 'a.jpg', at: 9 });
    expect(reduce(initialState, { type: 'event', event: { type: 'picture_current', ts: 9 } }).frame).toBeNull();
  });

  it('the connection status is kept beside the session', () => {
    const state = reduce(play([started]), { type: 'connection', status: 'reconnecting' });
    expect(state.connection).toBe('reconnecting');
    expect(state.session?.id).toBe('default');
  });

  it('notices get increasing ids, so each can be shown once', () => {
    const state = play([
      started,
      { type: 'download_saved', name: 'a.pdf', size: 1, ts: T0 },
      { type: 'download_saved', name: 'b.pdf', size: 1, ts: T0 },
    ]);
    expect(state.notices.map((notice) => notice.id)).toEqual([1, 2]);
  });

  const download = (name: string): ServerEvent => ({ type: 'download_saved', name, size: 1, ts: T0 });
  const unseen = (state: ViewerState) => unseenNotices(state).map((notice) => notice.id);

  it('what happened before the viewer caught up is not shown as new; what comes after is', () => {
    const before = play([started, download('a.pdf')]);
    expect(unseen(before)).toEqual([]);
    const caughtUp = reduce(before, { type: 'caught_up' });
    expect(unseen(caughtUp)).toEqual([]);
    expect(unseen(play([download('b.pdf')], caughtUp))).toEqual([2]);
  });

  it('a session that starts after the viewer caught up shows its notices as new', () => {
    const state = play([started, download('a.pdf')], reduce(initialState, { type: 'caught_up' }));
    expect(unseen(state)).toEqual([1]);
  });

  it('a connection that comes back replays the session, and none of it is shown as new', () => {
    let state = play([download('b.pdf')], reduce(play([started, download('a.pdf')]), { type: 'caught_up' }));
    expect(unseen(state)).toEqual([2]);
    state = reduce(state, { type: 'connection', status: 'reconnecting' });
    state = reduce(state, { type: 'connection', status: 'connected' });
    state = play([started, download('a.pdf'), download('b.pdf')], state);
    expect(unseen(state)).toEqual([]);
    state = reduce(state, { type: 'caught_up' });
    expect(unseen(state)).toEqual([]);
    expect(state.notices.map((notice) => notice.id)).toEqual([1, 2]);
    expect(unseen(play([download('c.pdf')], state))).toEqual([3]);
  });

  it('state is never changed in place', () => {
    const before = play([started]);
    const snapshot = JSON.stringify(before);
    play([stepStarted(1, 'browser_navigate', 'Opening a'), stepFinished(1, 'Opened a')], before);
    expect(JSON.stringify(before)).toBe(snapshot);
  });
});
