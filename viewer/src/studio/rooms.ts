// The pages of the window (spec 9.16): one for each browser the agent can work in.

import type { Backend } from '../protocol';

export interface Room {
  id: string;
  backend: Backend;
  /** Who is driving, as the session says it; or, with no session yet, `starting`, `waiting` or `failed`. */
  state: string;
  /** The agent waits for the person: a request for help, or an approval. */
  attention: boolean;
  working: boolean;
  /** Why the browser could not be started. */
  note?: string;
  /** For the person's own Chrome: the folder the extension is in, to load it from. */
  extension?: string;
}

const BACKENDS = new Set<string>(['remote_headless', 'takeover_chrome', 'bundled_chromium']);
/** The states in which a page has no session to show yet. */
const NO_SESSION = new Set(['starting', 'waiting', 'failed']);

export const hasSession = (room: Room): boolean => !NO_SESSION.has(room.state);

function roomOf(given: unknown): Room | null {
  if (typeof given !== 'object' || given === null) return null;
  const { id, backend, state, attention, working, note, extension } = given as Record<string, unknown>;
  if (typeof id !== 'string' || typeof backend !== 'string' || !BACKENDS.has(backend) || typeof state !== 'string') return null;
  return {
    id,
    backend: backend as Backend,
    state,
    attention: attention === true,
    working: working === true,
    note: typeof note === 'string' ? note : undefined,
    extension: typeof extension === 'string' ? extension : undefined,
  };
}

/** The rooms in what the service answered. Null when it has none: it shows one session, not a window of pages. */
export function roomsIn(answer: unknown): Room[] | null {
  const listed = typeof answer === 'object' && answer !== null ? (answer as { rooms?: unknown }).rooms : undefined;
  if (!Array.isArray(listed)) return null;
  const rooms = listed.map(roomOf).filter((room): room is Room => room !== null);
  return rooms.length > 0 ? rooms : null;
}

export type LoadRooms = () => Promise<Room[] | null>;

/** Asks the service which pages it has. The token goes in a header, never in the address. */
export function roomsFrom(pageAddress: string, token: string): LoadRooms {
  const address = new URL('api/sessions', pageAddress).href;
  return async () => {
    try {
      const answer = await fetch(address, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
      return answer.ok ? roomsIn(await answer.json()) : null;
    } catch {
      // The service is not answering just now. What was known stays on screen.
      return null;
    }
  };
}
