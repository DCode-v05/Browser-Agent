// Where the viewer's events come from and where its commands go. The components never know
// whether that is a recorded session or the service's WebSocket.

import type { ClientCommand, ServerEvent } from '../protocol';
import type { ConnectionStatus } from '../state/reducer';

export interface ConnectionHandlers {
  onEvent(event: ServerEvent): void;
  /** A new picture of the browser. `at` is on the session's clock, in seconds. */
  onFrame(src: string, at: number): void;
  onStatus(status: ConnectionStatus): void;
}

export interface Connection {
  start(handlers: ConnectionHandlers): void;
  send(command: ClientCommand): void;
  /** The session's clock, in seconds. Event times and picture times are on this clock. */
  now(): number;
  close(): void;
}
