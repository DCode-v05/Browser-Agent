// The live connection: one WebSocket to the session service (spec 4.8). Text messages are events,
// binary messages are picture frames, and the first message the viewer sends carries the token.

import type { ClientCommand, ServerEvent } from '../protocol';
import type { Connection, ConnectionHandlers } from './connection';

/** The part of a WebSocket this connection uses. */
export interface SocketLike {
  binaryType: string;
  readyState: number;
  send(data: string): void;
  close(): void;
  onopen: (() => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onclose: ((event: { code?: number }) => void) | null;
}

export interface SocketOptions {
  /** The session's WebSocket address. The token is never part of it. */
  url: string;
  token: string;
  createSocket?: (url: string) => SocketLike;
  /** How long to wait before each new attempt after the connection is lost. The last delay repeats. */
  reconnectMs?: number[];
}

const OPEN = 1;
const FRAME = 1;
/** The close code the service uses for a token it does not accept. */
const REFUSED = 4401;
const DEFAULT_RECONNECT_MS = [500, 1000, 2000, 5000];

export class SocketConnection implements Connection {
  private readonly createSocket: (url: string) => SocketLike;
  private readonly reconnectMs: number[];
  private handlers: ConnectionHandlers | undefined;
  private socket: SocketLike | undefined;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private attempt = 0;
  private closed = false;
  /** Seconds to add to this machine's clock to get the service's clock. */
  private clockOffset = 0;
  /** False while the service replays what had already happened. The replay carries no pictures. */
  private caughtUp = false;
  private session: string | undefined;
  private lastFrame: Blob | undefined;
  private live: string | undefined;
  /** Each finished step's picture, by step number. They outlive the live picture and a lost connection. */
  private readonly kept = new Map<number, string>();

  constructor(private readonly options: SocketOptions) {
    this.createSocket = options.createSocket ?? ((url) => new WebSocket(url) as unknown as SocketLike);
    this.reconnectMs = options.reconnectMs ?? DEFAULT_RECONNECT_MS;
  }

  start(handlers: ConnectionHandlers): void {
    this.handlers = handlers;
    this.closed = false;
    this.attempt = 0;
    handlers.onStatus('connecting');
    this.open();
  }

  send(command: ClientCommand): void {
    if (this.socket?.readyState === OPEN) this.socket.send(JSON.stringify(command));
  }

  now(): number {
    return Date.now() / 1000 + this.clockOffset;
  }

  close(): void {
    this.closed = true;
    clearTimeout(this.retry);
    this.socket?.close();
    if (this.live) URL.revokeObjectURL(this.live);
    this.live = undefined;
    this.lastFrame = undefined;
    this.releaseKept();
  }

  private open(): void {
    const socket = this.createSocket(this.options.url);
    this.socket = socket;
    socket.binaryType = 'arraybuffer';
    socket.onopen = () => {
      this.attempt = 0;
      this.caughtUp = false;
      // What was on screen before the connection was lost says nothing about a step that finishes now.
      this.lastFrame = undefined;
      socket.send(JSON.stringify({ type: 'auth', token: this.options.token }));
      this.handlers?.onStatus('connected');
    };
    socket.onmessage = (message) => this.receive(message.data);
    socket.onclose = (event) => {
      if (this.closed) return;
      if (event.code === REFUSED) {
        this.handlers?.onStatus('refused');
        return;
      }
      this.handlers?.onStatus('reconnecting');
      const delay = this.reconnectMs[Math.min(this.attempt, this.reconnectMs.length - 1)];
      this.attempt += 1;
      this.retry = setTimeout(() => this.open(), delay);
    };
  }

  private receive(data: unknown): void {
    if (data instanceof ArrayBuffer) {
      const bytes = new Uint8Array(data);
      if (bytes[0] === FRAME) this.showFrame(new Blob([bytes.subarray(1)], { type: 'image/jpeg' }));
      return;
    }
    if (typeof data !== 'string') return;
    const event = parse(data);
    if (!event) return;
    switch (event.type) {
      case 'caught_up':
        if (typeof event.ts === 'number') this.clockOffset = event.ts - Date.now() / 1000;
        this.caughtUp = true;
        this.handlers?.onCaughtUp?.();
        return;
      case 'session_started':
        if (event.session !== this.session) this.releaseKept();
        this.session = typeof event.session === 'string' ? event.session : undefined;
        break;
      case 'step_finished':
        if (typeof event.step === 'number') {
          this.handlers?.onEvent(event as ServerEvent, this.pictureFor(event.step));
          return;
        }
    }
    this.handlers?.onEvent(event as ServerEvent);
  }

  private showFrame(frame: Blob): void {
    const replaced = this.live;
    this.lastFrame = frame;
    this.live = URL.createObjectURL(frame);
    this.handlers?.onFrame(this.live, this.now());
    if (replaced) URL.revokeObjectURL(replaced);
  }

  /** A step that finishes now keeps its own copy of the picture. A replayed step keeps the one it had. */
  private pictureFor(step: number): string | undefined {
    if (this.caughtUp && this.lastFrame) this.kept.set(step, URL.createObjectURL(this.lastFrame));
    return this.kept.get(step);
  }

  private releaseKept(): void {
    for (const url of this.kept.values()) URL.revokeObjectURL(url);
    this.kept.clear();
  }
}

type Message = { type: string } & Record<string, unknown>;

function parse(text: string): Message | null {
  try {
    const value: unknown = JSON.parse(text);
    if (typeof value === 'object' && value !== null && 'type' in value && typeof value.type === 'string') {
      return value as Message;
    }
  } catch {
    // Not an event. The connection carries on.
  }
  return null;
}
