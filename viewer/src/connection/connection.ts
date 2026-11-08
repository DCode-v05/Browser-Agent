import type { ClientCommand, ServerEvent } from '../protocol';
import type { ConnectionStatus } from '../state/reducer';

export interface ConnectionHandlers {
  onEvent(event: ServerEvent, picture?: string): void;
  onFrame(src: string, at: number): void;
  onStatus(status: ConnectionStatus): void;
  onCaughtUp?(): void;
}

export interface Connection {
  start(handlers: ConnectionHandlers): void;
  send(command: ClientCommand): void;
  now(): number;
  close(): void;
}
