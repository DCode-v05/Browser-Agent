import type { Backend } from '../protocol';

export interface Room {
  id: string;
  backend: Backend;
  state: string;
  attention: boolean;
  working: boolean;
  note?: string;
  extension?: string;
  runs?: string;
  hand?: boolean;
  engineSystem?: string;
  drivenSystem?: string;
}

const BACKENDS = new Set<string>(['remote_headless', 'takeover_chrome', 'bundled_chromium', 'contained_desktop']);
const NO_SESSION = new Set(['starting', 'waiting', 'failed', 'off']);

export const hasSession = (room: Pick<Room, 'state'>): boolean => !NO_SESSION.has(room.state);

function roomOf(given: unknown): Room | null {
  if (typeof given !== 'object' || given === null) return null;
  const { id, backend, state, attention, working, note, extension, runs, hand, engine_system: engineSystem, driven_system: drivenSystem } = given as Record<string, unknown>;
  if (typeof id !== 'string' || typeof backend !== 'string' || !BACKENDS.has(backend) || typeof state !== 'string') return null;
  return {
    id,
    backend: backend as Backend,
    state,
    attention: attention === true,
    working: working === true,
    note: typeof note === 'string' ? note : undefined,
    extension: typeof extension === 'string' ? extension : undefined,
    runs: typeof runs === 'string' ? runs : undefined,
    hand: hand === true ? true : undefined,
    engineSystem: typeof engineSystem === 'string' ? engineSystem : undefined,
    drivenSystem: typeof drivenSystem === 'string' ? drivenSystem : undefined,
  };
}

export function roomsIn(answer: unknown): Room[] | null {
  const listed = typeof answer === 'object' && answer !== null ? (answer as { rooms?: unknown }).rooms : undefined;
  if (!Array.isArray(listed)) return null;
  const rooms = listed.map(roomOf).filter((room): room is Room => room !== null);
  return rooms.length > 0 ? rooms : null;
}

function pagesIn(answer: unknown): Room[] | null {
  const listed = typeof answer === 'object' && answer !== null ? (answer as { rooms?: unknown }).rooms : undefined;
  return Array.isArray(listed) ? (roomsIn(answer) ?? []) : null;
}

export type LoadRooms = () => Promise<Room[] | null>;
export type OpenDesktop = () => Promise<boolean>;

export interface ServiceFacts {
  rooms: Room[] | null;
  desktop: boolean;
  settings: boolean;
  systems: boolean;
}

export const NO_FACTS: ServiceFacts = { rooms: null, desktop: false, settings: false, systems: false };

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

export function besideOpener(pageAddress: string, token: string, inTheBrowser: (room: string) => void): (room: string) => Promise<void> {
  return async (room) => {
    const address = new URL(`api/sessions/${encodeURIComponent(room)}/beside`, pageAddress).href;
    try {
      if ((await fetch(address, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' })).ok) return;
    } catch {
    }
    inTheBrowser(room);
  };
}

export function roomsFrom(pageAddress: string, token: string, onEnded?: () => void): LoadRooms {
  const address = new URL('api/sessions', pageAddress).href;
  return async () => {
    try {
      const answer = await fetch(address, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
      if (answer.status === 401) onEnded?.();
      return answer.ok ? pagesIn(await answer.json()) : null;
    } catch {
      return null;
    }
  };
}
