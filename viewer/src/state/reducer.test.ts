import { describe, expect, it } from 'vitest';

import type { ServerEvent, TaskSite } from '../protocol';
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
      restartable: false,
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
    expect(state.approval).toEqual({ id: 'a7', tool: 'browser_upload_file', summary: 'Upload cv.pdf to example.com', site: 'example.com', everyTime: false, requestedAt: T0 + 20, expiresAt: T0 + 200 });
  });

  it('a request for an action that pays, sends or deletes is marked as asked about every time', () => {
    expect(play([started, { ...requested, every_time: true }]).approval?.everyTime).toBe(true);
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

describe('Auto Mode and safeguards (spec 18.10)', () => {
  const sites: TaskSite[] = [{ host: 'example.com', grade: 'named' }];

  it('nothing is shown of the mode before an auto_changed arrives', () => {
    expect(initialState.auto).toBeNull();
  });

  it('auto_changed keeps the mode, the run state and why', () => {
    const state = play([started, { type: 'auto_changed', mode: 'auto', state: 'paused', why: '3 steps in a row were refused', ts: T0 + 5 }]);
    expect(state.auto).toEqual({ mode: 'auto', state: 'paused', why: '3 steps in a row were refused' });
  });

  it('a task is set, and its line goes away when the task ends; the sites stay in sites_changed', () => {
    const set = play([started, { type: 'task_set', task: 'Check in for flight SK4821', from: 'person', sites, ts: T0 + 1 }]);
    expect(set.task).toEqual({ task: 'Check in for flight SK4821', from: 'person', sites });
    const changed = play([{ type: 'sites_changed', sites: [...sites, { host: 'maps.example', grade: 'added_read' }] }], set);
    expect(changed.task?.sites).toHaveLength(2);
    const ended = play([{ type: 'task_ended', ts: T0 + 2 }], changed);
    expect(ended.task).toBeNull();
  });

  it('sites_changed with no task does nothing', () => {
    expect(play([started, { type: 'sites_changed', sites }]).task).toBeNull();
  });

  it('a task declared by an agent is marked as that', () => {
    expect(play([started, { type: 'task_set', task: 'Buy the cheapest flight', from: 'agent', sites, ts: T0 + 1 }]).task?.from).toBe('agent');
  });

  it('check_decided marks the step "checked" when the reviewer lets it run', () => {
    const state = play([started, stepStarted(4, 'browser_click', 'Clicking "Search"'), { type: 'check_decided', step: 4, stage: 'reviewer', outcome: 'run', findings: [], reason: '', ts: T0 + 4 }]);
    expect(state.steps[0].mark).toEqual({ kind: 'checked' });
  });

  it('a rule that settles it without the reviewer carries no mark', () => {
    const state = play([started, stepStarted(4, 'browser_click', 'Clicking "Search"'), { type: 'check_decided', step: 4, stage: 'rule', outcome: 'run', findings: [], reason: '', ts: T0 + 4 }]);
    expect(state.steps[0].mark).toBeUndefined();
  });

  it('a refused step is marked with the reason and joins the "Refused" list, with "Allow once" where an id is given', () => {
    const state = play([
      started,
      stepStarted(6, 'browser_upload_file', 'Uploading cv.pdf'),
      {
        type: 'check_decided',
        step: 6,
        stage: 'reviewer',
        outcome: 'refuse',
        findings: ['sending_step'],
        reason: 'this step would send something to other people, and the task did not ask for it',
        refused_id: 'r1',
        ts: T0 + 6,
      },
    ]);
    expect(state.steps[0].mark).toEqual({ kind: 'refused', reason: 'this step would send something to other people, and the task did not ask for it' });
    expect(state.refused).toEqual([
      { step: 6, id: 'r1', label: 'Uploading cv.pdf', reason: 'this step would send something to other people, and the task did not ask for it', allowed: false },
    ]);
  });

  it('a hard stop refusal has no id, so it has no "Allow once" button', () => {
    const state = play([started, stepStarted(2, 'browser_navigate', 'Opening 10.0.0.5'), { type: 'check_decided', step: 2, stage: 'rule', outcome: 'refuse', findings: ['listed_bad_site'], reason: 'the site is known bad', ts: T0 + 2 }]);
    expect(state.refused[0].id).toBeNull();
  });

  it('"Allow once" marks the refused entry as allowed, by its id', () => {
    const refused = play([
      started,
      stepStarted(6, 'browser_upload_file', 'Uploading cv.pdf'),
      { type: 'check_decided', step: 6, stage: 'reviewer', outcome: 'refuse', findings: [], reason: 'refused', refused_id: 'r1', ts: T0 + 6 },
    ]);
    const allowed = play([{ type: 'refused_allowed', id: 'r1', ts: T0 + 7 }], refused);
    expect(allowed.refused[0].allowed).toBe(true);
  });

  it('an approval carries why it is asked, what leaves, the amount and the check\'s sentence', () => {
    const state = play([
      started,
      {
        type: 'approval_requested',
        id: 'a1',
        tool: 'browser_upload_file',
        summary: 'Upload cv.pdf to example.com',
        site: 'example.com',
        expires_in_s: 180,
        why: ['this step sends a file to another site'],
        leaves: { text: 'Lovelace, Ada', from_site: 'mail.example', to_site: 'example.com' },
        amount: '$84.00',
        said: 'The task does not mention a payment.',
        ts: T0 + 1,
      },
    ]);
    expect(state.approval).toMatchObject({
      why: ['this step sends a file to another site'],
      leaves: { text: 'Lovelace, Ada', fromSite: 'mail.example', toSite: 'example.com' },
      amount: '$84.00',
      said: 'The task does not mention a payment.',
    });
  });

  it('the step that waited for an approval is marked "you allowed" once it is allowed, not when it is denied', () => {
    const requested: ServerEvent = { type: 'approval_requested', id: 'a1', tool: 'browser_upload_file', summary: 'Upload cv.pdf', site: 'example.com', expires_in_s: 180, ts: T0 + 6 };
    const allowed = play([started, stepStarted(6, 'browser_upload_file', 'Uploading cv.pdf'), requested, { type: 'approval_closed', id: 'a1', outcome: 'allowed' }]);
    expect(allowed.steps[0].mark).toEqual({ kind: 'allowed' });
    const denied = play([started, stepStarted(6, 'browser_upload_file', 'Uploading cv.pdf'), requested, { type: 'approval_closed', id: 'a1', outcome: 'denied' }]);
    expect(denied.steps[0].mark).toBeUndefined();
  });

  it('a flagged page is kept, with an id that grows', () => {
    const state = play([
      started,
      { type: 'page_flagged', tab: 't1', site: 'shop.example', rule: 'planted_instruction', count: 1, ts: T0 + 1 },
      { type: 'page_flagged', tab: 't1', site: 'shop.example', rule: 'planted_instruction', count: 2, ts: T0 + 2 },
    ]);
    expect(state.flagged).toEqual([
      { id: 1, tab: 't1', site: 'shop.example' },
      { id: 2, tab: 't1', site: 'shop.example' },
    ]);
  });

  it('a limit reached is kept until it is lifted, or the session ends', () => {
    const reached = play([started, { type: 'limit_reached', kind: 'calls', limit: 500, scope: 'task', more: 100, ts: T0 + 1 }]);
    expect(reached.limit).toEqual({ kind: 'calls', limit: 500, scope: 'task', more: 100 });
    expect(play([{ type: 'limit_lifted', ts: T0 + 2 }], reached).limit).toBeNull();
    expect(play([{ type: 'session_ended', reason: 'person', ts: T0 + 2 }], reached).limit).toBeNull();
  });

  it('questions that ran out unanswered are kept as timeline markers', () => {
    const state = play([started, { type: 'questions_unanswered', count: 3, ts: T0 + 1 }, { type: 'questions_unanswered', count: 1, ts: T0 + 2 }]);
    expect(state.unanswered.map((marker) => marker.count)).toEqual([3, 1]);
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
