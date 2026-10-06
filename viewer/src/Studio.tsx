// One window, three browsers (spec 9.16): the cloud browser, the person's own Chrome and the built-in
// browser, each a page with its own session and its own chat. The tabs say where each one stands, so
// a page that needs the person is seen from any other.

import { useCallback, useEffect, useState } from 'react';

import { App, type AppProps } from './App';
import { Icon, type IconName } from './components/Icon';
import { Button } from './components/StatusPanel';
import type { Connection } from './connection/connection';
import type { Backend } from './protocol';
import { hasSession, type LoadRooms, type Room } from './studio/rooms';
import { W } from './wording';

const BACKEND_ICON: Record<Backend, IconName> = {
  remote_headless: 'globe',
  takeover_chrome: 'person',
  bundled_chromium: 'monitor',
};

export type RoomMood = 'attention' | 'working' | 'ready' | 'person' | 'paused' | 'stopped' | 'off';

/** Where a page stands, in one word and one colour. */
export function moodOf(room: Room): RoomMood {
  if (room.attention) return 'attention';
  if (!hasSession(room)) return 'off';
  if (room.state === 'ended') return 'stopped';
  if (room.state === 'paused') return 'paused';
  if (room.state === 'person') return 'person';
  return room.working ? 'working' : 'ready';
}

function wordFor(room: Room): string {
  const mood = moodOf(room);
  if (mood === 'off') return W.studio.off[room.state === 'failed' ? 'failed' : room.state === 'waiting' ? 'waiting' : 'starting'];
  return W.studio.mood[mood];
}

export interface StudioProps extends Omit<AppProps, 'createConnection' | 'embedded'> {
  /** The pages as the service listed them when the window opened. */
  rooms: Room[];
  loadRooms: LoadRooms;
  /** Opens the connection of one page's session. */
  connectionFor(room: string): Connection;
  /** How often the service is asked where the pages stand, in milliseconds. 0 asks once. */
  pollMs: number;
  /** The page to open on. */
  opensOn?: string;
  onPage?(room: string): void;
}

export function Studio({ rooms: given, loadRooms, connectionFor, pollMs, opensOn, onPage, ...app }: StudioProps) {
  const [rooms, setRooms] = useState(given);
  const [chosen, setChosen] = useState(opensOn);
  const room = rooms.find((one) => one.id === chosen) ?? rooms[0];

  useEffect(() => {
    if (!pollMs) return;
    let current = true;
    const timer = setInterval(async () => {
      const now = await loadRooms();
      if (current && now) setRooms(now);
    }, pollMs);
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [loadRooms, pollMs]);

  const createConnection = useCallback(() => connectionFor(room.id), [connectionFor, room.id]);
  const open = (id: string) => {
    setChosen(id);
    onPage?.(id);
  };

  return (
    <div className="studio">
      <header className="studio-bar">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{W.product}</span>
        </span>
        <div className="studio-tabs" role="tablist" aria-label={W.studio.pages}>
          {rooms.map((one) => (
            <button
              key={one.id}
              type="button"
              role="tab"
              id={`studio-tab-${one.id}`}
              className="studio-tab"
              aria-selected={one.id === room.id}
              aria-controls="studio-page"
              data-mood={moodOf(one)}
              onClick={() => open(one.id)}
            >
              <Icon name={BACKEND_ICON[one.backend]} />
              <span className="studio-tab-name">{W.backend[one.backend]}</span>
              <span className="studio-tab-mood">
                <span className="studio-tab-dot" aria-hidden="true" />
                {wordFor(one)}
              </span>
            </button>
          ))}
        </div>
      </header>
      <div className="studio-page" id="studio-page" role="tabpanel" aria-labelledby={`studio-tab-${room.id}`}>
        {hasSession(room) ? (
          // A page keeps nothing of the page before it: each has its own session.
          <App key={room.id} {...app} createConnection={createConnection} embedded />
        ) : (
          <NoSession room={room} />
        )}
      </div>
    </div>
  );
}

/** What a page shows while its browser is not there yet. */
function NoSession({ room }: { room: Room }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(room.extension ?? '');
      setCopied(true);
    } catch {
      // No clipboard here: the folder is on screen to be read.
    }
  };
  if (room.backend === 'takeover_chrome' && room.state !== 'failed') {
    return (
      <section className="studio-wait" aria-label={W.studio.connect.title}>
        <Icon name="plug" size="large" />
        <h2 className="studio-wait-title">{W.studio.connect.title}</h2>
        <p className="studio-wait-lead">{W.studio.connect.lead}</p>
        <ol className="studio-steps">
          <li>{W.studio.connect.open}</li>
          <li>
            {W.studio.connect.load}
            {room.extension && (
              <span className="studio-folder">
                <code>{room.extension}</code>
                <Button onClick={copy}>{copied ? W.studio.connect.copied : W.studio.connect.copy}</Button>
              </span>
            )}
          </li>
          <li>{W.studio.connect.icon}</li>
        </ol>
        <p className="studio-wait-note">{room.note ?? W.studio.connect.byItself}</p>
      </section>
    );
  }
  const failed = room.state === 'failed';
  return (
    <section className="studio-wait" aria-label={W.backend[room.backend]}>
      <Icon name={failed ? 'alert' : BACKEND_ICON[room.backend]} size="large" />
      <h2 className="studio-wait-title">{failed ? W.studio.failed : W.studio.starting}</h2>
      {room.note && <p className="studio-wait-lead">{room.note}</p>}
    </section>
  );
}
