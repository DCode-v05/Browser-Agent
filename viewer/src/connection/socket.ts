import { PAGE } from '../options';
import type { ClientCommand, ServerEvent } from '../protocol';
import type { Connection, ConnectionHandlers } from './connection';

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
  url: string;
  token: string;
  createSocket?: (url: string) => SocketLike;
  reconnectMs?: number[];
  releaseAfterMs?: number;
  inFront?: InFront;
}

export interface InFront {
  now(): boolean;
  onChange(listener: () => void): () => void;
}

const THE_DOCUMENT: InFront = {
  now: () => typeof document === 'undefined' || document.visibilityState === 'visible',
  onChange: (listener) => {
    if (typeof document === 'undefined') return () => undefined;
    document.addEventListener('visibilitychange', listener);
    return () => document.removeEventListener('visibilitychange', listener);
  },
};

const WIRE = { open: 1, picture: 1 } as const;
const FINAL = [4401, 4404];
const DEFAULT_RECONNECT_MS = [500, 1000, 2000, 5000];

export class SocketConnection implements Connection {
  private readonly createSocket: (url: string) => SocketLike;
  private readonly reconnectMs: number[];
  private readonly releaseAfterMs: number;
  private handlers: ConnectionHandlers | undefined;
  private socket: SocketLike | undefined;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private attempt = 0;
  private closed = false;
  private clockOffset = 0;
  private caughtUp = false;
  private session: string | undefined;
  private lastFrame: Blob | undefined;
  private live: string | undefined;
  private readonly leaving = new Map<string, ReturnType<typeof setTimeout>>();
  private readonly kept = new Map<number, string>();
  private readonly inFront: InFront;
  private stopSeeing: (() => void) | undefined;

  constructor(private readonly options: SocketOptions) {
    this.createSocket = options.createSocket ?? ((url) => new WebSocket(url) as unknown as SocketLike);
    this.reconnectMs = options.reconnectMs ?? DEFAULT_RECONNECT_MS;
    this.releaseAfterMs = options.releaseAfterMs ?? PAGE.releaseAfterMs;
    this.inFront = options.inFront ?? THE_DOCUMENT;
  }

  private sayWhetherSeen(): void {
    this.send({ type: 'seen', visible: this.inFront.now() });
  }

  start(handlers: ConnectionHandlers): void {
    this.handlers = handlers;
    this.closed = false;
    this.attempt = 0;
    handlers.onStatus('connecting');
    this.stopSeeing?.();
    this.stopSeeing = this.inFront.onChange(() => this.sayWhetherSeen());
    this.open();
  }

  send(command: ClientCommand): void {
    if (this.socket?.readyState === WIRE.open) this.socket.send(JSON.stringify(command));
  }

  now(): number {
    return Date.now() / 1000 + this.clockOffset;
  }

  close(): void {
    this.closed = true;
    this.stopSeeing?.();
    this.stopSeeing = undefined;
    clearTimeout(this.retry);
    this.socket?.close();
    for (const [url, timer] of this.leaving) {
      clearTimeout(timer);
      URL.revokeObjectURL(url);
    }
    this.leaving.clear();
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
      this.lastFrame = undefined;
      socket.send(JSON.stringify({ type: 'auth', token: this.options.token }));
      this.sayWhetherSeen();
      this.handlers?.onStatus('connected');
    };
    socket.onmessage = (message) => this.receive(message.data);
    socket.onclose = (event) => {
      if (this.closed) return;
      if (event.code !== undefined && FINAL.includes(event.code)) {
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
      if (bytes[0] === WIRE.picture) this.showFrame(new Blob([bytes.subarray(1)], { type: 'image/jpeg' }));
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
    if (replaced) {
      this.leaving.set(
        replaced,
        setTimeout(() => {
          this.leaving.delete(replaced);
          URL.revokeObjectURL(replaced);
        }, this.releaseAfterMs),
      );
    }
  }

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
  }
  return null;
}
