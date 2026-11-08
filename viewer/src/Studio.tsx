import { useCallback, useEffect, useRef, useState } from 'react';

import { App, type AppProps } from './App';
import { DEFAULT_PREFERENCES, preferencesFrom, type Preferences } from './preferences';
import type { Role } from './auth/api';
import { Icon, type IconName } from './components/Icon';
import { Button } from './components/StatusPanel';
import type { Connection } from './connection/connection';
import type { Backend } from './protocol';
import { hasSession, type LoadRooms, type OpenDesktop, type Room } from './studio/rooms';
import type { Passwords } from './systems/Access';
import { openingTheChatWithATask } from './studio/beside';
import { EngineMark, WhereLine } from './studio/WhereLine';
import type { Me, SystemsApi } from './systems/api';
import { SystemPanel, SystemsPage } from './systems/SystemsPage';
import { MachineSetup } from './MachineSetup';
import { W } from './wording';
import { TheWords, wordsFor } from './words';

const BACKEND_ICON: Record<Backend, IconName> = {
  remote_headless: 'globe',
  takeover_chrome: 'person',
  bundled_chromium: 'monitor',
  contained_desktop: 'computer',
};

export type RoomView = 'agent' | 'configuration' | 'settings' | 'evaluations';

function viewsFor(role: Role, me: Me | null | undefined): RoomView[] {
  if (role === 'admin') return ['agent', 'configuration', 'evaluations'];
  return me?.sees.evaluations ? ['agent', 'settings', 'evaluations'] : ['agent', 'settings'];
}

const onAMachine = (room: Room): boolean => hasSession(room) && (room.runs === 'machine' || room.runs === 'remote');

export type RoomMood = 'attention' | 'working' | 'ready' | 'person' | 'paused' | 'stopped' | 'off';

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

function useStartsPreferred(systems: SystemsApi | undefined, room: string, state: string | undefined) {
  const startedFor = useRef('');
  useEffect(() => {
    if (!systems || !room) return;
    if (state !== 'ended') {
      startedFor.current = '';
    } else if (startedFor.current !== room) {
      startedFor.current = room;
      void systems.manage(room, 'start');
    }
  }, [systems, room, state]);
}

const samePreferences = (one: Preferences, other: Preferences) => one.colourMode === other.colourMode && one.showAgentPointer === other.showAgentPointer;

export interface StudioProps extends Omit<AppProps, 'createConnection' | 'embedded' | 'onOpenSettings'> {
  rooms: Room[];
  loadRooms: LoadRooms;
  connectionFor(room: string): Connection;
  pollMs: number;
  opensOn?: string;
  onPage?(room: string): void;
  openDesktop?: OpenDesktop;
  openBeside?(room: string): void;
  systems?: SystemsApi;
  role?: Role;
  me?: Me | null;
  onSignOut?(): void;
  passwords?: Passwords;
}

export function Studio({ rooms: given, loadRooms, connectionFor, pollMs, opensOn, onPage, openDesktop, openBeside, systems, role = 'admin', me: givenMe, onSignOut, passwords, ...app }: StudioProps) {
  const [rooms, setRooms] = useState(given);
  const [me, setMe] = useState(givenMe);
  const [chosen, setChosen] = useState(role === 'user' ? (givenMe?.preferred ?? opensOn) : opensOn);
  const [onSystems, setOnSystems] = useState(false);
  const [wanted, setView] = useState<RoomView>('agent');
  const views = viewsFor(role, me);
  const view = views.includes(wanted) ? wanted : 'agent';
  const room = rooms.find((one) => one.id === chosen) ?? (rooms[0] as Room | undefined);
  const roomId = room?.id ?? '';
  useStartsPreferred(role === 'user' && roomId === me?.preferred ? systems : undefined, roomId, room?.state);

  const [preferences, setPreferences] = useState(app.preferences ?? DEFAULT_PREFERENCES);
  const prefers = useCallback((next: Preferences) => setPreferences((was) => (samePreferences(was, next) ? was : next)), []);
  useEffect(() => {
    const root = document.documentElement;
    if (preferences.colourMode === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', preferences.colourMode);
    return () => root.removeAttribute('data-theme');
  }, [preferences.colourMode]);

  const { settings, surface = 'web' } = app;
  const follows = role === 'user' ? systems : undefined;
  useEffect(() => {
    if (!pollMs) return;
    let current = true;
    const timer = setInterval(async () => {
      const [now, mine, set] = await Promise.all([loadRooms(), follows ? follows.me() : null, systems ? settings.load(surface).catch(() => null) : null]);
      if (!current) return;
      if (now) setRooms(now);
      if (mine) setMe(mine);
      if (set) prefers(preferencesFrom(set));
    }, pollMs);
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [loadRooms, pollMs, follows, systems, settings, surface, prefers]);

  const followsTheTask = Boolean(openBeside && room && onAMachine(room));
  const createConnection = useCallback(
    () => (followsTheTask && openBeside ? openingTheChatWithATask(connectionFor(roomId), () => openBeside(roomId)) : connectionFor(roomId)),
    [connectionFor, roomId, followsTheTask, openBeside],
  );
  const open = (id: string) => {
    setOnSystems(false);
    setChosen(id);
    onPage?.(id);
  };
  const refresh = useCallback(async () => {
    const now = await loadRooms();
    if (now) setRooms(now);
  }, [loadRooms]);
  const showingSystems = onSystems && systems !== undefined && role === 'admin';
  const named = wordsFor(showingSystems ? undefined : room?.backend).product;
  useEffect(() => {
    document.title = named;
  }, [named]);
  const prefer = async (id: string) => {
    const told = await systems?.prefer(id);
    if (!told) return;
    setMe(told);
    open(id);
    setView('agent');
    await refresh();
  };
  const side = (
    <span className="studio-side">
      {systems && role === 'admin' && (
        <Button
          icon="settings"
          kind={showingSystems ? 'primary' : 'plain'}
          hint={W.studio.hint.systems}
          onClick={() => {
            if (showingSystems) void refresh();
            setOnSystems(!showingSystems);
          }}
        >
          {W.studio.systems}
        </Button>
      )}
      {openBeside && room && onAMachine(room) && (
        <Button icon="computer" hint={W.studio.hint.beside} onClick={() => openBeside(room.id)}>
          {W.studio.beside.open}
        </Button>
      )}
      {openDesktop && <DesktopButton open={openDesktop} />}
    </span>
  );
  const account = onSignOut && (
    <span className="studio-side">
      <span className="studio-role" data-role={role}>
        <Icon name={role === 'admin' ? 'settings' : 'person'} />
        {W.signIn.role[role]}
      </span>
      <Button icon="close" hint={W.studio.hint.signOut} onClick={onSignOut}>
        {W.studio.signOut}
      </Button>
    </span>
  );

  if (!room) {
    return (
      <div className="studio">
        <header className="studio-bar">
          <h1 className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">{W.product}</span>
          </h1>
          {side}
          {account}
        </header>
        <main className="studio-page">
          <section className="studio-wait" aria-label={W.studio.noBrowser}>
            <Icon name="lock" size="large" />
            <h2 className="studio-wait-title">{W.studio.noBrowser}</h2>
            <p className="studio-wait-lead">{W.studio.noBrowserLead}</p>
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="studio">
      <header className="studio-bar">
        <h1 className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{named}</span>
        </h1>
        <EngineMark system={room.engineSystem} />
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
              title={W.studio.hint.backend[one.backend]}
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
        {account}
      </header>
      <nav className="studio-views">
        {systems && !showingSystems && (
          <div className="systems-views" role="tablist" aria-label={W.studio.views(W.backend[room.backend])}>
            {views.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                className="systems-view"
                aria-selected={view === name}
                title={wordsFor(room.backend).studio.hint.view[name]}
                onClick={() => {
                  if (name === 'agent') void refresh();
                  setView(name);
                }}
              >
                {name === 'agent' && room.backend === 'contained_desktop' ? W.studio.computer.view : W.studio.view[name]}
              </button>
            ))}
          </div>
        )}
        {side}
      </nav>
      {room.backend === 'contained_desktop' && hasSession(room) && !showingSystems && (
        <WhereLine runs={room.runs} settings={systems?.settings(room.id)} surface={surface} systems={{ engine: room.engineSystem, driven: room.drivenSystem }} />
      )}
      {onAMachine(room) && !room.hand && view === 'agent' && !showingSystems && room.state.startsWith('person') && (
        <p className="system-note studio-own-hands" role="status">
          {W.studio.beside.yourOwnHands}
        </p>
      )}
      <main className="studio-page">
       <div className="studio-panel" id="studio-page" role="tabpanel" aria-labelledby={showingSystems ? undefined : `studio-tab-${room.id}`} aria-label={showingSystems ? W.systems.title : undefined}>
        <TheWords.Provider value={wordsFor(showingSystems ? undefined : room.backend)}>
        {showingSystems ? (
          <SystemsPage
            api={systems}
            pollMs={pollMs}
            wordFor={wordFor}
            passwords={passwords}
            onOpen={(id, next) => {
              open(id);
              setView(next);
            }}
          />
        ) : systems && view !== 'agent' ? (
          <SystemPanel
            key={room.id}
            api={systems}
            system={room.id}
            view={view}
            role={role}
            me={me}
            onPrefer={(id) => void prefer(id)}
            surface={surface}
            pollMs={pollMs}
            wordFor={wordFor}
            onChanged={() => void refresh()}
            onSettings={(answer) => prefers(preferencesFrom(answer))}
          />
        ) : hasSession(room) ? (
          <App
            key={room.id}
            {...app}
            preferences={preferences}
            settings={systems ? systems.settings(room.id) : settings}
            createConnection={createConnection}
            onOpenSettings={systems ? () => setView(role === 'admin' ? 'configuration' : 'settings') : undefined}
            embedded
            inWindow
          />
        ) : (
          <NoSession
            room={room}
            onTurnOn={systems && role === 'admin' ? () => systems.settings(room.id).change(surface, { system_enabled: true }).then(refresh, refresh) : undefined}
            onManage={systems && role === 'admin' ? (step) => systems.manage(room.id, step) : undefined}
          />
        )}
        </TheWords.Provider>
       </div>
      </main>
    </div>
  );
}

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
      <Button icon="monitor" hint={W.studio.hint.desktop} onClick={press} disabled={state === 'opening'}>
        {W.studio.desktop.open}
      </Button>
    </span>
  );
}

function NoSession({ room, onTurnOn, onManage }: { room: Room; onTurnOn?(): void; onManage?(step: 'install' | 'allow'): Promise<{ ok: true } | { ok: false; why: string }> }) {
  const [copied, setCopied] = useState(false);
  if (room.backend === 'contained_desktop' && room.runs === 'machine' && room.state !== 'off') {
    return <MachineSetup note={room.note} onManage={onManage} />;
  }
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(room.extension ?? '');
      setCopied(true);
    } catch {
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
                <Button hint={W.buttons.hint.copyFolder} onClick={copy}>
                  {copied ? W.studio.connect.copied : W.studio.connect.copy}
                </Button>
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
    return (
      <section className="studio-wait" aria-label={W.backend[room.backend]}>
        <Icon name="pause" size="large" />
        <h2 className="studio-wait-title">{room.backend === 'contained_desktop' ? W.studio.computer.turnedOff : W.studio.turnedOff}</h2>
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
  const words = room.backend === 'contained_desktop' ? W.studio.computer : W.studio;
  return (
    <section className="studio-wait" aria-label={W.backend[room.backend]}>
      <Icon name={failed ? 'alert' : BACKEND_ICON[room.backend]} size="large" />
      <h2 className="studio-wait-title">{failed ? words.failed : words.starting}</h2>
      {room.note && <p className="studio-wait-lead">{room.note}</p>}
    </section>
  );
}
