import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App, preferencesFrom } from './App';
import { Studio } from './Studio';
import { desktopOpener, factsFrom, NO_FACTS, roomsFrom } from './studio/rooms';
import { systemsFrom } from './systems/api';
import { W } from './wording';
import { socketAddress, takeToken } from './connection/address';
import type { Connection } from './connection/connection';
import { DemoConnection } from './connection/demo';
import { SocketConnection } from './connection/socket';
import { SESSIONS, STATES } from './demo/sessions';
import { createDemoSettings } from './demo/settings';
import { settingsFrom } from './settings/api';
import type { SettingsAnswer, SettingsSource } from './settings/types';
import type { Surface } from './protocol';
import './tokens.css';
import './styles/base.css';
import './styles/app.css';
import './styles/settings.css';

const HEARTBEAT_MS = 2000;
/** How often the window asks the service where its pages stand. */
const ROOMS_MS = 1500;
const PAGE_KEY = 'bap-browser.page';
/** What the viewer keeps by itself when the service it shows has no settings to give (spec 10.2). */
const KEPT_BY_THE_VIEWER = ['colour_mode', 'show_agent_pointer'];

const query = new URLSearchParams(location.search);
const named = query.get('surface');
const surface: Surface = named === 'mobile' || named === 'desktop' ? named : 'web';

// `?state=` and `?demo=` play a recorded session. Anything else is a live session, which needs its token.
const state = query.get('state');
const demo = query.get('demo');
const recorded = state !== null || demo !== null;
const recording = (state && STATES[state]) || SESSIONS[demo ?? 'signup'] || SESSIONS.signup;
const pace = state ? 0 : Number(query.get('pace') ?? 1);

const tabStorage = {
  getItem: (key: string) => sessionStorage.getItem(key),
  setItem: (key: string, value: string) => sessionStorage.setItem(key, value),
};
const token = recorded ? null : takeToken(location, tabStorage, (address) => history.replaceState(null, '', address));

// A link opened in a tab that already shows the viewer changes only what follows the #, and the
// browser does not load the page again by itself. Loading it again takes the new token in.
if (!recorded) {
  window.addEventListener('hashchange', () => {
    if (new URLSearchParams(location.hash.slice(1)).get('token')) location.reload();
  });
}

function connectionFor(session: string): Connection {
  return new SocketConnection({ url: socketAddress(location.href, session), token: token ?? '' });
}

function createConnection(): Connection {
  if (recorded) return new DemoConnection(recording, { pace, heartbeatMs: HEARTBEAT_MS });
  if (token) return connectionFor(query.get('session') ?? 'default');
  // Opened without its token: there is no session this page may show.
  return { start: (handlers) => handlers.onStatus('refused'), send: () => undefined, now: () => Date.now() / 1000, close: () => undefined };
}

// What the service has, asked once: the window then asks for nothing the service does not have.
const facts = token && !recorded ? await factsFrom(location.href, token) : NO_FACTS;

// A live session's settings are the service's. A recorded one plays with settings of its own, and a
// service that has none to give leaves the viewer the two that are the viewer's.
let settings: SettingsSource = recorded ? createDemoSettings() : token && facts.settings ? settingsFrom(location.href, token) : createDemoSettings(KEPT_BY_THE_VIEWER);
let loaded: SettingsAnswer;
try {
  loaded = await settings.load(surface);
} catch {
  // The service did not answer just now. The page still opens.
  settings = createDemoSettings(KEPT_BY_THE_VIEWER);
  loaded = await settings.load(surface);
}

const preferences = preferencesFrom(loaded);
const theme = query.get('theme');
if (theme === 'light' || theme === 'dark') preferences.colourMode = theme;

// A service that has several browsers shows them as pages of one window (spec 9.16). A link that
// names a session shows that session alone, as the extension's side panel does.
const loadRooms = token && !recorded && !query.has('session') ? roomsFrom(location.href, token) : null;
const rooms = loadRooms ? facts.rooms : null;
const openDesktop = rooms && token && facts.desktop ? desktopOpener(location.href, token) : undefined;
const systems = rooms && token && facts.systems ? systemsFrom(location.href, token, W.systems.unreachable) : undefined;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {rooms && loadRooms ? (
      <Studio
        rooms={rooms}
        loadRooms={loadRooms}
        connectionFor={connectionFor}
        pollMs={ROOMS_MS}
        opensOn={tabStorage.getItem(PAGE_KEY) ?? undefined}
        onPage={(room) => tabStorage.setItem(PAGE_KEY, room)}
        openDesktop={openDesktop}
        systems={systems}
        settings={settings}
        surface={surface}
        preferences={preferences}
      />
    ) : (
      <App createConnection={createConnection} settings={settings} surface={surface} embedded={query.has('embed')} preferences={preferences} />
    )}
  </StrictMode>,
);
