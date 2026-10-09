// The pages of the window (spec 9.16): one for each browser the agent can work in.

import type { Backend } from '../protocol';

export interface Room {
  id: string;
  backend: Backend;
  /** Who is driving, as the session says it; or, with no session, `starting`, `waiting`, `failed` or `off`. */
  state: string;
  /** The agent waits for the person: a request for help, or an approval. */
  attention: boolean;
  working: boolean;
  /** Why the browser could not be started. */
  note?: string;
  /** For the person's own Chrome: the folder the extension is in, to load it from. */
  extension?: string;
}

const BACKENDS = new Set<string>(['remote_headless', 'takeover_chrome', 'bundled_chromium', 'contained_desktop']);
/** The states in which a page has no session to show yet. */
const NO_SESSION = new Set(['starting', 'waiting', 'failed', 'off']);

export const hasSession = (room: Pick<Room, 'state'>): boolean => !NO_SESSION.has(room.state);

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

/**
 * The pages of a window, as the service lists them. A window may have none: a user the admin lets use
 * no browser (spec 4.11). Null is something else: a service that has one session and no window of pages.
 */
function pagesIn(answer: unknown): Room[] | null {
  const listed = typeof answer === 'object' && answer !== null ? (answer as { rooms?: unknown }).rooms : undefined;
  return Array.isArray(listed) ? (roomsIn(answer) ?? []) : null;
}

export type LoadRooms = () => Promise<Room[] | null>;
/** Asks the service to open the desktop app. True when its window is open. */
export type OpenDesktop = () => Promise<boolean>;

/** What a service says of itself when the window opens: its pages, and what it has besides. */
export interface ServiceFacts {
  /** Null when it shows one session, not a window of pages. */
  rooms: Room[] | null;
  /** It has a desktop app to open (spec 9.16). */
  desktop: boolean;
  /** It has the settings API (spec 10.2). Without it the viewer keeps the settings that are its own. */
  settings: boolean;
  /** Its browsers are systems to set up, manage and evaluate (spec 9.17). */
  systems: boolean;
}

export const NO_FACTS: ServiceFacts = { rooms: null, desktop: false, settings: false, systems: false };

/** Asks the service once, so that the window never asks for what the service does not have. */
export async function factsFrom(pageAddress: string, token: string): Promise<ServiceFacts> {
  try {
    const answer = await fetch(new URL('api/sessions', pageAddress).href, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    if (!answer.ok) return NO_FACTS;
    const told = (await answer.json()) as { desktop?: unknown; settings?: unknown; systems?: unknown };
    return { rooms: pagesIn(told), desktop: told.desktop === true, settings: told.settings === true, systems: told.systems === true };
  } catch {
    return NO_FACTS;
  }
}

/** The way to open the desktop app from the window (spec 9.16). */
export function desktopOpener(pageAddress: string, token: string): OpenDesktop {
  const address = new URL('api/desktop', pageAddress).href;
  return async () => {
    try {
      return (await fetch(address, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })).ok;
    } catch {
      return false;
    }
  };
}

/** Asks the service which pages it has. The token goes in a header, never in the address.
 *  `onEnded` is told when the service no longer knows the token: the visit it was for is over. */
export function roomsFrom(pageAddress: string, token: string, onEnded?: () => void): LoadRooms {
  const address = new URL('api/sessions', pageAddress).href;
  return async () => {
    try {
      const answer = await fetch(address, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
      if (answer.status === 401) onEnded?.();
      return answer.ok ? pagesIn(await answer.json()) : null;
    } catch {
      // The service is not answering just now. What was known stays on screen.
      return null;
    }
  };
}
