// One window, three browsers (spec 9.16): the cloud browser, the person's own Chrome and the built-in
// browser, each a page with its own session and its own chat. The tabs say where each one stands, so
// a page that needs the person is seen from any other.

import { useCallback, useEffect, useState } from 'react';

import { App, type AppProps } from './App';
import { Icon, type IconName } from './components/Icon';
import { Button } from './components/StatusPanel';
import type { Connection } from './connection/connection';
import type { Backend } from './protocol';
import { hasSession, type LoadRooms, type OpenDesktop, type Room } from './studio/rooms';
import type { SystemsApi } from './systems/api';
import { SystemPanel, SystemsPage } from './systems/SystemsPage';
import { W } from './wording';

const BACKEND_ICON: Record<Backend, IconName> = {
  remote_headless: 'globe',
  takeover_chrome: 'person',
  bundled_chromium: 'monitor',
};

/** What is shown under a browser's tab: the browser itself with its chat, how it is set up, or what its tasks took. */
export type RoomView = 'agent' | 'configuration' | 'evaluations';
const ROOM_VIEWS: RoomView[] = ['agent', 'configuration', 'evaluations'];

export type RoomMood = 'attention' | 'working' | 'ready' | 'person' | 'paused' | 'stopped' | 'off';

/** Where a page stands, in one word and one colour. */
export function moodOf(room: Pick<Room, 'state' | 'attention' | 'working'>): RoomMood {
  if (room.attention) return 'attention';
  if (!hasSession(room)) return 'off';
  if (room.state === 'ended') return 'stopped';
  if (room.state === 'paused') return 'paused';
  if (room.state === 'person') return 'person';
  return room.working ? 'working' : 'ready';
}

export function wordFor(room: Pick<Room, 'state' | 'attention' | 'working'>): string {
  const mood = moodOf(room);
  if (mood !== 'off') return W.studio.mood[mood];
  const state = room.state;
  return W.studio.off[state === 'failed' || state === 'waiting' || state === 'off' ? state : 'starting'];
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
  /** Opens the desktop app, where the service has one to open. */
  openDesktop?: OpenDesktop;
  /** The browsers as systems to set up, manage and evaluate (spec 9.17), where the service has them so. */
  systems?: SystemsApi;
}

export function Studio({ rooms: given, loadRooms, connectionFor, pollMs, opensOn, onPage, openDesktop, systems, ...app }: StudioProps) {
  const [rooms, setRooms] = useState(given);
  const [chosen, setChosen] = useState(opensOn);
  /** The Systems page is shown in place of a browser's own page. */
  const [onSystems, setOnSystems] = useState(false);
  /** What is shown under the chosen browser's tab. It stays as it is from one browser to the next. */
  const [view, setView] = useState<RoomView>('agent');
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
    setOnSystems(false);
    setChosen(id);
    onPage?.(id);
  };
  // A browser that was turned on or off shows so at once, not at the next time the service is asked.
  const refresh = useCallback(async () => {
    const now = await loadRooms();
    if (now) setRooms(now);
  }, [loadRooms]);
  const showingSystems = onSystems && systems !== undefined;

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
              aria-selected={!showingSystems && one.id === room.id}
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
        <span className="studio-side">
          {systems && (
            <Button
              icon="settings"
              kind={showingSystems ? 'primary' : 'plain'}
              onClick={() => {
                if (showingSystems) void refresh();
                setOnSystems(!showingSystems);
              }}
            >
              {W.studio.systems}
            </Button>
          )}
          {openDesktop && <DesktopButton open={openDesktop} />}
        </span>
      </header>
      {systems && !showingSystems && (
        // Under each browser: the browser itself, how it is set up, and what its tasks took (spec 9.17).
        <nav className="studio-views">
          <div className="systems-views" role="tablist" aria-label={W.studio.views(W.backend[room.backend])}>
            {ROOM_VIEWS.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                className="systems-view"
                aria-selected={view === name}
                onClick={() => {
                  // Back on the browser's own page, it shows where the browser stands now.
                  if (name === 'agent') void refresh();
                  setView(name);
                }}
              >
                {W.studio.view[name]}
              </button>
            ))}
          </div>
        </nav>
      )}
      <div className="studio-page" id="studio-page" role="tabpanel" aria-labelledby={showingSystems ? undefined : `studio-tab-${room.id}`} aria-label={showingSystems ? W.systems.title : undefined}>
        {showingSystems ? (
          <SystemsPage api={systems} surface={app.surface ?? 'web'} pollMs={pollMs} wordFor={wordFor} />
        ) : systems && view !== 'agent' ? (
          <SystemPanel key={room.id} api={systems} system={room.id} view={view} surface={app.surface ?? 'web'} pollMs={pollMs} wordFor={wordFor} onChanged={() => void refresh()} />
        ) : hasSession(room) ? (
          // A page keeps nothing of the page before it: each has its own session, and settings of its own.
          <App key={room.id} {...app} settings={systems ? systems.settings(room.id) : app.settings} createConnection={createConnection} embedded />
        ) : (
          <NoSession room={room} onTurnOn={systems ? () => systems.settings(room.id).change(app.surface ?? 'web', { system_enabled: true }).then(refresh, refresh) : undefined} />
        )}
      </div>
    </div>
  );
}

/** Opens the desktop app: a window of its own, with its own browser and its own chat (spec 14.3). */
function DesktopButton({ open }: { open: OpenDesktop }) {
  const [state, setState] = useState<'idle' | 'opening' | 'opened' | 'failed'>('idle');
  const press = async () => {
    setState('opening');
    setState((await open()) ? 'opened' : 'failed');
  };
  return (
    <span className="studio-desktop">
      {state !== 'idle' && (
        <span className="studio-desktop-note" role="status">
          {W.studio.desktop[state]}
        </span>
      )}
      <Button icon="monitor" onClick={press} disabled={state === 'opening'}>
        {W.studio.desktop.open}
      </Button>
    </span>
  );
}

/** What a page shows while its browser is not there yet. */
function NoSession({ room, onTurnOn }: { room: Room; onTurnOn?(): void }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(room.extension ?? '');
      setCopied(true);
    } catch {
      // No clipboard here: the folder is on screen to be read.
    }
  };
  if (room.backend === 'takeover_chrome' && room.state !== 'failed' && room.state !== 'off') {
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
            {room.extension && <span className="studio-tip">{W.studio.connect.paste}</span>}
          </li>
          <li>{W.studio.connect.icon}</li>
        </ol>
        <p className="studio-wait-note">{room.note ?? W.studio.connect.byItself}</p>
      </section>
    );
  }
  if (room.state === 'off') {
    // A person turned this browser off (spec 9.17). It is turned on here, or on the Systems page.
    return (
      <section className="studio-wait" aria-label={W.backend[room.backend]}>
        <Icon name="pause" size="large" />
        <h2 className="studio-wait-title">{W.studio.turnedOff}</h2>
        <p className="studio-wait-lead">{W.studio.turnedOffLead}</p>
        {onTurnOn && (
          <Button kind="primary" icon="play" onClick={onTurnOn}>
            {W.studio.turnOn}
          </Button>
        )}
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
