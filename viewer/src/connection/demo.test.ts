import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ClientCommand, ServerEvent } from '../protocol';
import { DemoConnection, type Beat, type RecordedSession } from './demo';

const START = 1_000;

function started(): Beat {
  return {
    after: 100,
    event: { type: 'session_started', session: 'demo', agent: 'Demo agent', backend: 'remote_headless', browser: 'Chromium', viewport: { width: 1280, height: 800 } },
  };
}

function stepStart(n: number, after = 1000): Beat {
  return { after, event: { type: 'step_started', step: n, tool: 'browser_click', label: `Clicking ${n}` } };
}

function stepEnd(n: number, after = 200, ok = true, frame?: string): Beat {
  return { after, frame, event: { type: 'step_finished', step: n, ok, ms: after, chars: 10, summary: ok ? `Clicked ${n}` : `Could not click ${n}`, url: 'https://example.com/' } };
}

const APPROVAL: Beat = {
  after: 100,
  event: { type: 'approval_requested', id: 'a1', tool: 'browser_upload_file', summary: 'Upload cv.pdf to example.com', site: 'example.com', expires_in_s: 180 },
  approval: { allowed: [stepEnd(2, 300, true, 'file.jpg')], denied: [stepEnd(2, 50, false)] },
};

const HELP: Beat = {
  after: 100,
  event: { type: 'help_requested', id: 'h1', reason: 'enter the code', kind: 'verification', expires_in_s: 900 },
  help: { done: [stepEnd(2, 300, true, 'after.jpg')], couldNot: [stepEnd(2, 50, false)], personFrame: 'typing.jpg' },
};

function run(beats: Beat[], options: { pace?: number; afterwards?: RecordedSession['afterwards']; auto?: RecordedSession['auto']; commands?: ClientCommand[] } = {}) {
  const events: ServerEvent[] = [];
  const frames: string[] = [];
  const statuses: string[] = [];
  const connection = new DemoConnection(
    { name: 'test', beats, afterwards: options.afterwards, auto: options.auto, commands: options.commands },
    { pace: options.pace ?? 1, startAt: START, realNow: () => Date.now() },
  );
  connection.start({
    onEvent: (event) => events.push(event),
    onFrame: (src) => frames.push(src),
    onStatus: (status) => statuses.push(status),
  });
  const types = () => events.map((event) => (event.type === 'control_changed' ? `control:${event.state}` : event.type));
  return { connection, events, frames, statuses, types };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(0);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('playing a recorded session', () => {
  it('says it is connected, then emits each beat after its delay, in order', () => {
    const { types, statuses } = run([started(), stepStart(1), stepEnd(1)]);
    expect(statuses).toEqual(['connected']);
    expect(types()).toEqual([]);
    vi.advanceTimersByTime(100);
    expect(types()).toEqual(['session_started']);
    vi.advanceTimersByTime(999);
    expect(types()).toEqual(['session_started']);
    vi.advanceTimersByTime(1);
    expect(types()).toEqual(['session_started', 'step_started']);
    vi.advanceTimersByTime(200);
    expect(types()).toEqual(['session_started', 'step_started', 'step_finished']);
  });

  it('stamps events on the session clock, which follows the recording', () => {
    const { events, connection } = run([started(), stepStart(1, 12_000)]);
    vi.advanceTimersByTime(12_100);
    expect(events[0]).toMatchObject({ type: 'session_started', ts: START + 0.1 });
    expect(events[1]).toMatchObject({ type: 'step_started', ts: START + 12.1 });
    vi.advanceTimersByTime(3000);
    expect(connection.now()).toBeCloseTo(START + 15.1, 5);
  });

  it('a picture arrives before the event it belongs to', () => {
    const order: string[] = [];
    const connection = new DemoConnection({ name: 'test', beats: [started(), stepStart(1), stepEnd(1, 200, true, 'one.jpg')] }, { pace: 1, startAt: START, realNow: () => Date.now() });
    connection.start({ onEvent: (event) => order.push(event.type), onFrame: (src) => order.push(src), onStatus: () => undefined });
    vi.advanceTimersByTime(2000);
    expect(order).toEqual(['session_started', 'step_started', 'one.jpg', 'step_finished']);
  });

  it('at pace 0 it plays at once, keeping the recorded gaps on the clock', () => {
    const { events, types } = run([started(), stepStart(1), stepEnd(1), stepStart(2, 14_000)], { pace: 0 });
    expect(types()).toEqual(['session_started', 'step_started', 'step_finished', 'step_started']);
    expect(events[3]).toMatchObject({ ts: START + 0.1 + 1 + 0.2 + 14 });
  });

  it('closing stops it', () => {
    const { connection, types } = run([started(), stepStart(1)]);
    vi.advanceTimersByTime(100);
    connection.close();
    vi.advanceTimersByTime(60_000);
    expect(types()).toEqual(['session_started']);
  });

  it('can end in a lost connection, for the disconnected state', () => {
    const { statuses } = run([started()], { pace: 0, afterwards: 'reconnecting' });
    expect(statuses).toEqual(['connected', 'reconnecting']);
  });
});

describe('keeping the picture current', () => {
  function withHeartbeat(session: RecordedSession) {
    const types: string[] = [];
    const connection = new DemoConnection(session, { pace: 0, startAt: START, realNow: () => Date.now(), heartbeatMs: 2000 });
    connection.start({ onEvent: (event) => types.push(event.type), onFrame: () => undefined, onStatus: () => undefined });
    return { connection, types };
  }

  it('says the picture is still current at once and then every heartbeat, as the service does for a still page', () => {
    const { types } = withHeartbeat({ name: 'test', beats: [started()] });
    expect(types).toEqual(['session_started', 'picture_current']);
    vi.advanceTimersByTime(4000);
    expect(types).toEqual(['session_started', 'picture_current', 'picture_current', 'picture_current']);
  });

  it('a recording that stalls sends none, so its picture goes stale', () => {
    const { types } = withHeartbeat({ name: 'test', beats: [started()], stalls: true });
    vi.advanceTimersByTime(10_000);
    expect(types).toEqual(['session_started']);
  });

  it('stops when the session ends', () => {
    const { connection, types } = withHeartbeat({ name: 'test', beats: [started()] });
    connection.send({ type: 'stop' });
    vi.advanceTimersByTime(10_000);
    expect(types).toEqual(['session_started', 'picture_current', 'session_ended']);
  });
});

describe('approvals', () => {
  const beats = [started(), stepStart(2), APPROVAL, stepStart(3)];

  it('waits for the person at an approval', () => {
    const { types } = run(beats);
    vi.advanceTimersByTime(60_000);
    expect(types()).toEqual(['session_started', 'step_started', 'approval_requested', 'control:waiting_approval']);
  });

  it.each([
    ['once', 'allowed'],
    ['site', 'allowed_site'],
  ] as const)('allow (%s) closes it, gives control back and carries on down the allowed branch', (scope, outcome) => {
    const { connection, events, types, frames } = run(beats);
    vi.advanceTimersByTime(5000);
    connection.send({ type: 'approve', id: 'a1', scope });
    expect(events.at(-2)).toMatchObject({ type: 'approval_closed', id: 'a1', outcome });
    expect(types().at(-1)).toBe('control:agent');
    vi.advanceTimersByTime(300);
    expect(events.at(-1)).toMatchObject({ type: 'step_finished', step: 2, ok: true });
    expect(frames).toEqual(['file.jpg']);
    vi.advanceTimersByTime(1000);
    expect(events.at(-1)).toMatchObject({ type: 'step_started', step: 3 });
  });

  it('deny carries on down the denied branch', () => {
    const { connection, events } = run(beats);
    vi.advanceTimersByTime(5000);
    connection.send({ type: 'deny', id: 'a1' });
    vi.advanceTimersByTime(50);
    expect(events.at(-1)).toMatchObject({ type: 'step_finished', step: 2, ok: false });
  });

  it('no answer in time means denied', () => {
    const { events, types } = run(beats);
    vi.advanceTimersByTime(1200 + 180_000);
    expect(types().slice(-2)).toEqual(['approval_closed', 'control:agent']);
    expect(events.at(-2)).toMatchObject({ outcome: 'expired' });
    vi.advanceTimersByTime(50);
    expect(events.at(-1)).toMatchObject({ type: 'step_finished', ok: false });
  });

  it('an answer for another approval is ignored', () => {
    const { connection, types } = run(beats);
    vi.advanceTimersByTime(5000);
    connection.send({ type: 'approve', id: 'nope', scope: 'once' });
    expect(types().at(-1)).toBe('control:waiting_approval');
  });

  it('a recording can answer for the person, to reach a later state at once', () => {
    const { types } = run(beats, { pace: 0, auto: { approval: 'allow' } });
    expect(types()).toContain('approval_closed');
    expect(types().at(-1)).toBe('step_started');
  });
});

describe('pause, take over, stop', () => {
  const beats = [started(), stepStart(1), stepEnd(1), stepStart(2), stepEnd(2)];

  it('pause holds the recording; resume carries on', () => {
    const { connection, types } = run(beats);
    vi.advanceTimersByTime(1300);
    connection.send({ type: 'pause' });
    expect(types().at(-1)).toBe('control:paused');
    vi.advanceTimersByTime(60_000);
    expect(types().filter((type) => type === 'step_started')).toHaveLength(1);
    connection.send({ type: 'resume' });
    expect(types().at(-1)).toBe('control:agent');
    vi.advanceTimersByTime(1000);
    expect(types().at(-1)).toBe('step_started');
  });

  it('take over puts the person in control; hand back returns it to the agent', () => {
    const { connection, types } = run(beats);
    vi.advanceTimersByTime(1300);
    connection.send({ type: 'take_over' });
    expect(types().at(-1)).toBe('control:person');
    vi.advanceTimersByTime(60_000);
    expect(types().at(-1)).toBe('control:person');
    connection.send({ type: 'hand_back' });
    expect(types().at(-1)).toBe('control:agent');
    vi.advanceTimersByTime(1000);
    expect(types().at(-1)).toBe('step_started');
  });

  it('stop ends the session and nothing follows', () => {
    const { connection, events, types } = run(beats);
    vi.advanceTimersByTime(1300);
    connection.send({ type: 'stop' });
    expect(events.at(-1)).toMatchObject({ type: 'session_ended', reason: 'person' });
    connection.send({ type: 'resume' });
    vi.advanceTimersByTime(60_000);
    expect(types().at(-1)).toBe('session_ended');
  });

  it('the recording stops by itself at its end', () => {
    const { types } = run([...beats, { after: 500, event: { type: 'session_ended', reason: 'agent' } }]);
    vi.advanceTimersByTime(60_000);
    expect(types().at(-1)).toBe('session_ended');
  });

  it('a recording can carry commands, to reach a state such as paused at once', () => {
    const { types } = run([started(), stepStart(1), stepEnd(1)], { pace: 0, commands: [{ type: 'pause' }] });
    expect(types().at(-1)).toBe('control:paused');
  });
});

describe('requests for help', () => {
  const beats = [started(), stepStart(2), HELP, stepStart(3)];

  it('waits for the person', () => {
    const { types } = run(beats);
    vi.advanceTimersByTime(60_000);
    expect(types().slice(-2)).toEqual(['help_requested', 'control:person_requested']);
  });

  it('take over, then done, closes the request and carries on down the done branch', () => {
    const { connection, events, types, frames } = run(beats);
    vi.advanceTimersByTime(5000);
    connection.send({ type: 'take_over' });
    expect(types().at(-1)).toBe('control:person');
    connection.send({ type: 'key', action: 'down', key: '4', code: 'Digit4' });
    expect(frames).toEqual(['typing.jpg']);
    connection.send({ type: 'done' });
    expect(events.at(-2)).toMatchObject({ type: 'help_closed', id: 'h1', outcome: 'done' });
    expect(types().at(-1)).toBe('control:agent');
    vi.advanceTimersByTime(300);
    expect(events.at(-1)).toMatchObject({ type: 'step_finished', ok: true });
    expect(frames).toEqual(['typing.jpg', 'after.jpg']);
  });

  it("couldn't do it tells the agent", () => {
    const { connection, events } = run(beats);
    vi.advanceTimersByTime(5000);
    connection.send({ type: 'could_not' });
    expect(events.at(-2)).toMatchObject({ type: 'help_closed', outcome: 'could_not' });
    vi.advanceTimersByTime(50);
    expect(events.at(-1)).toMatchObject({ type: 'step_finished', ok: false });
  });

  it('handing back without an answer leaves the request open', () => {
    const { connection, types } = run(beats);
    vi.advanceTimersByTime(5000);
    connection.send({ type: 'take_over' });
    connection.send({ type: 'hand_back' });
    expect(types().at(-1)).toBe('control:person_requested');
  });

  it('no answer in time tells the agent', () => {
    const { events } = run(beats);
    vi.advanceTimersByTime(1200 + 900_000);
    expect(events.at(-2)).toMatchObject({ type: 'help_closed', outcome: 'timed_out' });
  });
});
