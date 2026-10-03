// Where the viewer's events come from and where its commands go. The components never know
// whether that is a recorded session or the service's WebSocket.

import type { ClientCommand, ServerEvent } from '../protocol';
import type { ConnectionStatus } from '../state/reducer';

export interface ConnectionHandlers {
  /** `picture` comes with a finished step: the browser as it was at that moment, kept for the step. */
  onEvent(event: ServerEvent, picture?: string): void;
  /** A new picture of the browser. `at` is on the session's clock, in seconds. */
  onFrame(src: string, at: number): void;
  onStatus(status: ConnectionStatus): void;
  /** Everything that had already happened has been replayed. What follows is new. */
  onCaughtUp?(): void;
}

export interface Connection {
  start(handlers: ConnectionHandlers): void;
  send(command: ClientCommand): void;
  /** The session's clock, in seconds. Event times and picture times are on this clock. */
  now(): number;
  close(): void;
}
