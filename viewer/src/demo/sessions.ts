// Recorded sessions (spec 9.11): one full run, and one short recording for each state of spec 9.3.
// The pictures and the boxes of the elements come from `scripts/record_demo.py`.

import type { Beat, EventDraft, RecordedSession } from '../connection/demo';
import type { Box } from '../protocol';
import boxes from './boxes.json';

const pictures = import.meta.glob<string>('./frames/*.jpg', { eager: true, query: '?url', import: 'default' });

function picture(name: string): string {
  const src = pictures[`./frames/${name}.jpg`];
  if (!src) throw new Error(`no recorded picture named ${name}`);
  return src;
}

const SIGNUP = 'https://example.com/signup';
const VERIFY = 'https://example.com/verify';
const HOME = 'https://example.com/home';

interface StepOptions {
  /** Milliseconds the agent takes before starting the step. */
  think?: number;
  /** Milliseconds the step takes. */
  takes?: number;
  target?: Box;
  frame?: string;
  url?: string;
  chars?: number;
  ok?: boolean;
}

function start(n: number, tool: string, label: string, options: StepOptions = {}): Beat {
  const event: EventDraft = { type: 'step_started', step: n, tool, label, ...(options.target ? { target: options.target } : {}) };
  return { after: options.think ?? 900, event };
}

function finish(n: number, summary: string, options: StepOptions = {}): Beat {
  const takes = options.takes ?? 320;
  return {
    after: takes,
    frame: options.frame ? picture(options.frame) : undefined,
    event: { type: 'step_finished', step: n, ok: options.ok ?? true, ms: takes, chars: options.chars ?? 62, summary, url: options.url ?? SIGNUP },
  };
}

function step(n: number, tool: string, label: string, summary: string, options: StepOptions = {}): Beat[] {
  return [start(n, tool, label, options), finish(n, summary, options)];
}

function tab(title: string, url: string): Beat {
  return { after: 0, event: { type: 'tab_changed', tabs: [{ id: 't1', title, url, active: true }] } };
}

const SESSION_STARTED: Beat = {
  after: 400,
  event: {
    type: 'session_started',
    session: 'default',
    agent: 'Claude Code',
    backend: 'remote_headless',
    browser: 'Chromium 153',
    viewport: { width: 1280, height: 800 },
  },
};

// Named points in the run, so the single-state recordings can stop exactly there.
const OPENING: Beat[] = [
  SESSION_STARTED,
  tab('New tab', 'about:blank'),
  ...step(1, 'browser_navigate', 'Opening example.com/signup', 'Opened example.com/signup', { think: 700, takes: 640, frame: '01-signup', chars: 612 }),
  tab('Sign up', SIGNUP),
  ...step(2, 'browser_snapshot', 'Reading the page', 'Read the page', { think: 500, takes: 4, chars: 598 }),
  ...step(3, 'browser_type', 'Typing 12 characters into "Full name"', 'Typed 12 characters into "Full name"', { target: boxes.name, frame: '02-name', takes: 9 }),
  ...step(4, 'browser_type', 'Typing 15 characters into "Email"', 'Typed 15 characters into "Email"', { target: boxes.email, frame: '03-email', takes: 8 }),
];

const CHOOSING_COUNTRY = start(5, 'browser_select_option', 'Choosing "India" in "Country"', { target: boxes.country });

const TO_UPLOAD: Beat[] = [
  CHOOSING_COUNTRY,
  finish(5, 'Chose "India" in "Country"', { frame: '04-country', takes: 6 }),
  start(6, 'browser_upload_file', 'Uploading cv.pdf', { target: boxes.cv }),
];

const APPROVAL: Beat = {
  after: 250,
  event: { type: 'approval_requested', id: 'a1', tool: 'browser_upload_file', summary: 'Upload cv.pdf to example.com', site: 'example.com', expires_in_s: 180 },
  approval: {
    allowed: [finish(6, 'Uploaded cv.pdf', { frame: '05-file', takes: 420 })],
    denied: [finish(6, 'Could not upload cv.pdf: a person did not approve it', { ok: false, takes: 60 })],
  },
};

const TO_VERIFY: Beat[] = [
  ...step(7, 'browser_click', 'Clicking "I accept the terms"', 'Clicked "I accept the terms" (checkbox)', { target: boxes.terms, frame: '06-terms', takes: 46 }),
  ...step(8, 'browser_click', 'Clicking "Create account"', 'Clicked "Create account" (button)', { target: boxes.create, frame: '07-verify', takes: 380, url: VERIFY }),
  tab('Verify your email', VERIFY),
  ...step(9, 'browser_snapshot', 'Reading the page', 'Read the page', { think: 400, takes: 3, chars: 286, url: VERIFY }),
  ...step(10, 'browser_get_text', 'Reading the page', 'Read the page', { think: 600, takes: 2, chars: 344, url: VERIFY }),
  start(11, 'browser_request_human', 'Asking for help', { think: 1100 }),
];

const HELP: Beat = {
  after: 200,
  event: { type: 'help_requested', id: 'h1', reason: 'enter the 6-digit code sent to ada@example.com', kind: 'verification', expires_in_s: 900 },
  help: {
    personFrame: picture('08-code'),
    done: [finish(11, 'Asked for help: "enter the 6-digit code". Done', { frame: '09-welcome', takes: 500, url: HOME, chars: 118 }), tab('Welcome, Ada', HOME)],
    couldNot: [
      finish(11, 'Asked for help: the person could not do it', { ok: false, takes: 80, url: VERIFY }),
      { after: 1400, event: { type: 'session_ended', reason: 'agent', detail: 'The agent stopped: it could not go on without the code.' } },
    ],
  },
};

const TO_BLOCKED: Beat[] = [
  ...step(12, 'browser_snapshot', 'Reading the page', 'Read the page', { think: 700, takes: 4, chars: 912, url: HOME }),
  start(13, 'browser_navigate', 'Opening 10.0.0.5/admin', { think: 1200 }),
  { after: 120, event: { type: 'navigation_blocked', url: 'http://10.0.0.5/admin', reason: 'private address' } },
  finish(13, 'Could not open 10.0.0.5/admin: private address', { ok: false, takes: 30, url: HOME, chars: 96 }),
];

const TO_DIALOG: Beat[] = [
  // The agent thinks for a while here, which shows as an idle divider.
  ...step(14, 'browser_click', 'Clicking "Download invoice"', 'Clicked "Download invoice" (link)', { think: 12_000, target: boxes.invoice, takes: 180, url: HOME }),
  { after: 300, event: { type: 'download_saved', name: 'INV-1042.pdf', size: 48_211 } },
  start(15, 'browser_click', 'Clicking "Account"', { think: 1300 }),
  { after: 260, event: { type: 'dialog_opened', id: 'd1', kind: 'confirm', text: 'Sign out of Northfield? Unsaved changes will be lost.', expires_in_s: 120 } },
];

const ENDING: Beat[] = [
  finish(15, 'Clicked "Account": a dialog opened', { takes: 40, url: HOME, chars: 104 }),
  start(16, 'browser_handle_dialog', 'Answering the dialog', { think: 1500 }),
  { after: 200, event: { type: 'dialog_closed', id: 'd1', outcome: 'dismissed' } },
  finish(16, 'Dismissed the dialog "Sign out of Northfield?"', { takes: 20, url: HOME }),
  { after: 1600, event: { type: 'session_ended', reason: 'agent' } },
];

const FULL_RUN: Beat[] = [...OPENING, ...TO_UPLOAD, APPROVAL, ...TO_VERIFY, HELP, ...TO_BLOCKED, ...TO_DIALOG, ...ENDING];

/** The whole run, at real pace. A person answers the approval and the request for help. */
export const SIGNUP_SESSION: RecordedSession = { name: 'signup', beats: FULL_RUN };

const TAKEOVER_CHROME_START: Beat = {
  after: 0,
  event: { ...(SESSION_STARTED.event as Extract<EventDraft, { type: 'session_started' }>), backend: 'takeover_chrome', browser: 'Chrome 154' },
};

/** One recording per state of spec 9.3 (and a few more), each stopping in that state. */
export const STATES: Record<string, RecordedSession> = {
  no_agent: { name: 'no_agent', beats: [] },
  empty: { name: 'empty', beats: [SESSION_STARTED, tab('New tab', 'about:blank')] },
  agent: { name: 'agent', beats: [...OPENING, CHOOSING_COUNTRY] },
  waiting_approval: { name: 'waiting_approval', beats: [...OPENING, ...TO_UPLOAD, APPROVAL] },
  person_requested: { name: 'person_requested', beats: [...OPENING, ...TO_UPLOAD, APPROVAL, ...TO_VERIFY, HELP], auto: { approval: 'allow' } },
  person: {
    name: 'person',
    beats: [...OPENING, ...TO_UPLOAD, APPROVAL, ...TO_VERIFY, HELP],
    auto: { approval: 'allow' },
    commands: [{ type: 'take_over' }],
  },
  person_unasked: { name: 'person_unasked', beats: [...OPENING, CHOOSING_COUNTRY], commands: [{ type: 'take_over' }] },
  paused: { name: 'paused', beats: [...OPENING, CHOOSING_COUNTRY, finish(5, 'Chose "India" in "Country"', { frame: '04-country', takes: 6 })], commands: [{ type: 'pause' }] },
  blocked: { name: 'blocked', beats: [...OPENING, ...TO_UPLOAD, APPROVAL, ...TO_VERIFY, HELP, ...TO_BLOCKED], auto: { approval: 'allow', help: 'done' } },
  dialog: {
    name: 'dialog',
    beats: [...OPENING, ...TO_UPLOAD, APPROVAL, ...TO_VERIFY, HELP, ...TO_BLOCKED, ...TO_DIALOG],
    auto: { approval: 'allow', help: 'done' },
  },
  denied: { name: 'denied', beats: [...OPENING, ...TO_UPLOAD, APPROVAL, start(7, 'browser_click', 'Clicking "I accept the terms"', { target: boxes.terms })], auto: { approval: 'deny' } },
  ended: { name: 'ended', beats: FULL_RUN, auto: { approval: 'allow', help: 'done' } },
  disconnected: { name: 'disconnected', beats: [...OPENING, CHOOSING_COUNTRY], afterwards: 'reconnecting' },
  // Eight quiet seconds after the last picture: longer than `viewer.stale_after_s`.
  stale: { name: 'stale', beats: [...OPENING, CHOOSING_COUNTRY, { after: 8000 }], stalls: true },
  own_browser: {
    name: 'own_browser',
    beats: [TAKEOVER_CHROME_START, tab('Sign up', SIGNUP), ...OPENING.slice(2).map((beat) => ({ ...beat, frame: undefined })), CHOOSING_COUNTRY],
  },
};

export const SESSIONS: Record<string, RecordedSession> = { signup: SIGNUP_SESSION };
