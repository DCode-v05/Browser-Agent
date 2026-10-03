import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { ServerEvent } from '../protocol';
import { SocketConnection, type SocketLike } from './socket';

class FakeSocket implements SocketLike {
  static all: FakeSocket[] = [];
  binaryType = '';
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code?: number }) => void) | null = null;

  constructor(readonly url: string) {
    FakeSocket.all.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = 3;
  }

  open(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  text(event: unknown): void {
    this.onmessage?.({ data: typeof event === 'string' ? event : JSON.stringify(event) });
  }

  frame(bytes: number[]): void {
    this.onmessage?.({ data: new Uint8Array([1, ...bytes]).buffer });
  }

  drop(code = 1006): void {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}

function connect() {
  const events: ServerEvent[] = [];
  const frames: string[] = [];
  /** The picture each finished step came with, by step number. */
  const pictures: Record<number, string | undefined> = {};
  const statuses: string[] = [];
  let caughtUp = 0;
  const connection = new SocketConnection({
    url: 'ws://127.0.0.1:8765/api/sessions/default/ws',
    token: 'secret-token',
    createSocket: (url) => new FakeSocket(url),
    reconnectMs: [500, 2000],
  });
  connection.start({
    onEvent: (event, picture) => {
      events.push(event);
      if (event.type === 'step_finished') pictures[event.step] = picture;
    },
    onFrame: (src) => frames.push(src),
    onStatus: (status) => statuses.push(status),
    onCaughtUp: () => (caughtUp += 1),
  });
  return { connection, events, frames, pictures, statuses, caughtUp: () => caughtUp, socket: () => FakeSocket.all.at(-1)! };
}

const started = (session: string) => ({
  type: 'session_started',
  session,
  agent: 'Reference agent',
  backend: 'remote_headless',
  browser: 'Chromium',
  viewport: { width: 1280, height: 800 },
  ts: 10,
});
const finished = (step: number) => ({ type: 'step_finished', step, ok: true, ms: 5, chars: 9, summary: 'Read the page', url: 'https://example.com/' });

let made = 0;
let revoked: string[] = [];

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(50_000);
  FakeSocket.all = [];
  made = 0;
  revoked = [];
  URL.createObjectURL = vi.fn(() => `blob:picture-${(made += 1)}`);
  URL.revokeObjectURL = vi.fn((url: string) => void revoked.push(url));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('connecting', () => {
  it('says it is connecting, then sends the token as its first message and says it is connected', () => {
    const { statuses, socket } = connect();
    expect(statuses).toEqual(['connecting']);
    expect(socket().url).toBe('ws://127.0.0.1:8765/api/sessions/default/ws');
    expect(socket().binaryType).toBe('arraybuffer');
    socket().open();
    expect(socket().sent).toEqual([JSON.stringify({ type: 'auth', token: 'secret-token' })]);
    expect(statuses).toEqual(['connecting', 'connected']);
  });

  it('the token is never part of the address', () => {
    const { socket } = connect();
    expect(socket().url).not.toContain('secret-token');
  });
});

describe('events', () => {
  it('passes each event on, in order', () => {
    const { events, socket } = connect();
    socket().open();
    socket().text({ type: 'control_changed', state: 'paused', since: 12 });
    socket().text({ type: 'tab_changed', tabs: [] });
    expect(events.map((event) => event.type)).toEqual(['control_changed', 'tab_changed']);
  });

  it('caught_up is told apart from the events, and sets the session clock to the service clock', () => {
    const { connection, events, caughtUp, socket } = connect();
    socket().open();
    socket().text({ type: 'caught_up', ts: 1_000_000 });
    expect(events).toEqual([]);
    expect(caughtUp()).toBe(1);
    expect(connection.now()).toBeCloseTo(1_000_000, 3);
    vi.advanceTimersByTime(2500);
    expect(connection.now()).toBeCloseTo(1_000_002.5, 3);
  });

  it('a message that is not an event is ignored', () => {
    const { events, socket } = connect();
    socket().open();
    socket().text('not json');
    socket().text('{"no":"type"}');
    socket().text('[1, 2]');
    expect(events).toEqual([]);
  });
});

describe('pictures', () => {
  it('a frame becomes a picture, and the picture it replaces is released', () => {
    const { frames, socket } = connect();
    socket().open();
    socket().frame([255, 216, 1]);
    socket().frame([255, 216, 2]);
    expect(frames).toEqual(['blob:picture-1', 'blob:picture-2']);
    expect(revoked).toEqual(['blob:picture-1']);
  });

  it('a finished step comes with its own copy of the picture on screen at that moment', () => {
    const { frames, pictures, socket } = connect();
    socket().open();
    socket().text({ type: 'caught_up', ts: 50 });
    socket().frame([255, 216, 1]);
    socket().text(finished(1));
    socket().frame([255, 216, 2]);
    socket().frame([255, 216, 3]);
    // picture-2 is the step's copy. Live pictures come and go around it; it stays.
    expect(pictures).toEqual({ 1: 'blob:picture-2' });
    expect(frames).toEqual(['blob:picture-1', 'blob:picture-3', 'blob:picture-4']);
    expect(revoked).toEqual(['blob:picture-1', 'blob:picture-3']);
  });

  it('a step that finishes before any picture arrived comes with none', () => {
    const { pictures, socket } = connect();
    socket().open();
    socket().text({ type: 'caught_up', ts: 50 });
    socket().text(finished(1));
    expect(pictures).toEqual({ 1: undefined });
  });

  it('a late viewer gets the old steps without pictures: the history carries none', () => {
    const { pictures, socket } = connect();
    socket().open();
    socket().text(started('default'));
    socket().text(finished(1));
    socket().frame([255, 216, 1]);
    socket().text({ type: 'caught_up', ts: 50 });
    socket().text(finished(2));
    expect(pictures).toEqual({ 1: undefined, 2: 'blob:picture-2' });
  });

  it('after the connection comes back, a replayed step keeps the picture it had; one that finished meanwhile has none', () => {
    const { pictures, socket } = connect();
    socket().open();
    socket().text(started('default'));
    socket().text({ type: 'caught_up', ts: 50 });
    socket().frame([255, 216, 1]);
    socket().text(finished(1));
    socket().drop();
    vi.advanceTimersByTime(500);
    socket().open();
    socket().text(started('default'));
    socket().text(finished(1));
    socket().text(finished(2));
    socket().text({ type: 'caught_up', ts: 60 });
    expect(pictures).toEqual({ 1: 'blob:picture-2', 2: undefined });
    expect(revoked).toEqual([]);
  });

  it("another session's pictures are released when a new session starts", () => {
    const { pictures, socket } = connect();
    socket().open();
    socket().text(started('first'));
    socket().text({ type: 'caught_up', ts: 50 });
    socket().frame([255, 216, 1]);
    socket().text(finished(1));
    socket().text(started('second'));
    expect(revoked).toEqual(['blob:picture-2']);
    socket().text(finished(1));
    expect(pictures).toEqual({ 1: 'blob:picture-3' });
  });

  it('a binary message that is not a frame is ignored', () => {
    const { frames, socket } = connect();
    socket().open();
    socket().onmessage?.({ data: new Uint8Array([9, 1, 2]).buffer });
    socket().onmessage?.({ data: new Uint8Array([]).buffer });
    expect(frames).toEqual([]);
  });
});

describe('commands', () => {
  it('are sent as JSON once connected, and dropped before that', () => {
    const { connection, socket } = connect();
    connection.send({ type: 'pause' });
    socket().open();
    connection.send({ type: 'approve', id: 'a1', scope: 'once' });
    expect(socket().sent.slice(1)).toEqual([JSON.stringify({ type: 'approve', id: 'a1', scope: 'once' })]);
  });
});

describe('a lost connection', () => {
  it('is reported, and retried after growing delays', () => {
    const { statuses, socket } = connect();
    socket().open();
    socket().drop();
    expect(statuses.at(-1)).toBe('reconnecting');
    vi.advanceTimersByTime(499);
    expect(FakeSocket.all).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.all).toHaveLength(2);
    socket().drop();
    vi.advanceTimersByTime(1999);
    expect(FakeSocket.all).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeSocket.all).toHaveLength(3);
    socket().drop();
    // The last delay is used from then on.
    vi.advanceTimersByTime(2000);
    expect(FakeSocket.all).toHaveLength(4);
  });

  it('signs in again when it comes back, and the delays start over', () => {
    const { statuses, socket } = connect();
    socket().open();
    socket().drop();
    vi.advanceTimersByTime(500);
    socket().open();
    expect(socket().sent).toEqual([JSON.stringify({ type: 'auth', token: 'secret-token' })]);
    expect(statuses.at(-1)).toBe('connected');
    socket().drop();
    vi.advanceTimersByTime(500);
    expect(FakeSocket.all).toHaveLength(3);
  });

  it('a refused token is reported as that, and is not tried again', () => {
    const { statuses, socket } = connect();
    socket().open();
    socket().drop(4401);
    expect(statuses.at(-1)).toBe('refused');
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.all).toHaveLength(1);
  });

  it('closing stops it for good and releases its pictures', () => {
    const { connection, statuses, socket } = connect();
    socket().open();
    socket().text({ type: 'caught_up', ts: 50 });
    socket().frame([255, 216, 1]);
    socket().text(finished(1));
    connection.close();
    expect(socket().readyState).toBe(3);
    socket().onclose?.({ code: 1000 });
    vi.advanceTimersByTime(60_000);
    expect(FakeSocket.all).toHaveLength(1);
    expect(statuses.at(-1)).toBe('connected');
    expect(revoked).toEqual(['blob:picture-1', 'blob:picture-2']);
  });
});
