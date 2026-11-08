import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { preferencesFrom } from './preferences';
import { authFrom, type AuthState, type Role } from './auth/api';
import { SignIn } from './auth/SignIn';
import { Studio } from './Studio';
import { EngineMark, WhereLine } from './studio/WhereLine';
import { besideOpener, desktopOpener, factsFrom, NO_FACTS, roomsFrom } from './studio/rooms';
import { systemsFrom, type Me } from './systems/api';
import { PAGE } from './options';
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

const PAGE_KEY = 'bap-browser.page';
const VISIT_KEY = 'bap-browser.visit';
const OPERATOR_KEY = 'bap-browser.token';
const LEAVING_KEY = 'bap-browser.leaving';
const KEPT_BY_THE_VIEWER = ['colour_mode', 'show_agent_pointer'];

const query = new URLSearchParams(location.search);
const named = query.get('surface');
const surface: Surface = named === 'mobile' || named === 'desktop' ? named : 'web';

const state = query.get('state');
const demo = query.get('demo');
const recorded = state !== null || demo !== null;
const recording = (state && STATES[state]) || SESSIONS[demo ?? 'signup'] || SESSIONS.signup;
const pace = state ? 0 : Number(query.get('pace') ?? 1);

const tabStorage = {
  getItem: (key: string) => {
    try {
      return sessionStorage.getItem(key);
    } catch {
      return null;
    }
  },
  setItem: (key: string, value: string) => {
    try {
      sessionStorage.setItem(key, value);
    } catch {
    }
  },
  removeItem: (key: string) => {
    try {
      sessionStorage.removeItem(key);
    } catch {
    }
  },
};
const atAdmin = /\/admin\/?$/.test(location.pathname);
const adminPage = atAdmin ? location.pathname : new URL('admin', location.href).pathname;
const userPage = atAdmin ? new URL('./', location.href).pathname : location.pathname;

const operator = recorded ? null : takeToken(location, tabStorage, (address) => history.replaceState(null, '', address));
const visit = recorded ? null : tabStorage.getItem(VISIT_KEY);
let token = visit ?? operator;
let role: Role = 'admin';
let signsIn = false;
let signInPage: { role: Role; state: AuthState } | null = null;

if (!recorded) {
  window.addEventListener('hashchange', () => {
    if (new URLSearchParams(location.hash.slice(1)).get('token')) location.reload();
  });
}

const auth = authFrom(location.href);
const leaving = recorded ? null : tabStorage.getItem(LEAVING_KEY);
if (leaving) {
  tabStorage.removeItem(LEAVING_KEY);
  await auth.signOut(leaving);
}
if (!recorded) {
  let known = await auth.state(token);
  if (known && known !== 'no_accounts' && known.role === null && visit && operator) {
    tabStorage.removeItem(VISIT_KEY);
    token = operator;
    known = await auth.state(token);
  }
  if (known && known !== 'no_accounts') {
    signsIn = true;
    const firstTime = atAdmin && known.operator && !known.admin_set;
    const mustSignIn = known.role === null || (atAdmin && known.role !== 'admin');
    if (firstTime || mustSignIn) signInPage = { role: atAdmin ? 'admin' : 'user', state: known };
    else role = known.role ?? 'admin';
  } else if (known === 'no_accounts') {
    token = operator;
  }
}

function signedIn(visitToken: string) {
  tabStorage.setItem(VISIT_KEY, visitToken);
  tabStorage.removeItem(OPERATOR_KEY);
  location.reload();
}

function signOut() {
  if (token) tabStorage.setItem(LEAVING_KEY, token);
  tabStorage.removeItem(VISIT_KEY);
  tabStorage.removeItem(OPERATOR_KEY);
  tabStorage.removeItem(PAGE_KEY);
  location.assign(role === 'admin' ? adminPage : userPage);
}

let ended = false;
function visitEnded() {
  if (ended) return;
  ended = true;
  tabStorage.removeItem(VISIT_KEY);
  tabStorage.removeItem(PAGE_KEY);
  location.reload();
}

function connectionFor(session: string): Connection {
  return new SocketConnection({ url: socketAddress(location.href, session), token: token ?? '' });
}

function createConnection(): Connection {
  if (recorded) return new DemoConnection(recording, { pace, heartbeatMs: PAGE.heartbeatMs });
  if (token) return connectionFor(query.get('session') ?? 'default');
  return { start: (handlers) => handlers.onStatus('refused'), send: () => undefined, now: () => Date.now() / 1000, close: () => undefined };
}

const live = !recorded && !signInPage && token ? token : null;

const facts = live ? await factsFrom(location.href, live) : NO_FACTS;

const sessionNamed = query.get('session');
const ownSettings = (token: string): SettingsSource =>
  sessionNamed && facts.systems ? systemsFrom(location.href, token, W.systems.unreachable).settings(sessionNamed) : settingsFrom(location.href, token);
let settings: SettingsSource = recorded ? createDemoSettings() : live && facts.settings ? ownSettings(live) : createDemoSettings(KEPT_BY_THE_VIEWER);
let loaded: SettingsAnswer;
try {
  loaded = await settings.load(surface);
} catch {
  settings = createDemoSettings(KEPT_BY_THE_VIEWER);
  loaded = await settings.load(surface);
}

const preferences = preferencesFrom(loaded);
const theme = query.get('theme');
if (theme === 'light' || theme === 'dark') preferences.colourMode = theme;

const loadRooms = live && !query.has('session') ? roomsFrom(location.href, live, signsIn && live === visit ? visitEnded : undefined) : null;
const rooms = loadRooms ? facts.rooms : null;
const openDesktop = rooms && live && facts.desktop ? desktopOpener(location.href, live) : undefined;
const besideInTheBrowser = (room: string) =>
  void window.open(`?session=${encodeURIComponent(room)}&beside`, `bap-browser-chat-${room}`, `popup,width=${PAGE.besideWidth},height=${PAGE.besideHeight}`);
const askForBeside = live ? besideOpener(location.href, live, besideInTheBrowser) : undefined;
const openBeside = (room: string) => void (askForBeside ? askForBeside(room) : besideInTheBrowser(room));
const systems = rooms && live && facts.systems ? systemsFrom(location.href, live, W.systems.unreachable) : undefined;
const me: Me | null = systems && signsIn ? await systems.me() : null;

const chatOf = query.has('beside') ? facts.rooms?.find((room) => room.id === query.get('session')) : undefined;
const whereOfTheChat = !chatOf ? undefined : chatOf.backend === 'contained_desktop' ? (
  <WhereLine runs={chatOf.runs} settings={facts.systems ? settings : undefined} surface={surface} systems={{ engine: chatOf.engineSystem, driven: chatOf.drivenSystem }} />
) : (
  <EngineMark system={chatOf.engineSystem} />
);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {signInPage ? (
      <SignIn role={signInPage.role} state={signInPage.state} api={auth} operator={operator} onSignedIn={signedIn} otherPage={signInPage.role === 'admin' ? userPage : adminPage} />
    ) : rooms && loadRooms ? (
      <Studio
        rooms={rooms}
        loadRooms={loadRooms}
        connectionFor={connectionFor}
        pollMs={PAGE.roomsPollMs}
        opensOn={tabStorage.getItem(PAGE_KEY) ?? undefined}
        onPage={(room) => tabStorage.setItem(PAGE_KEY, room)}
        openDesktop={openDesktop}
        openBeside={openBeside}
        systems={systems}
        role={role}
        me={me}
        onSignOut={signsIn ? signOut : undefined}
        passwords={signsIn && role === 'admin' && live ? { set: (whose, password) => auth.setPassword(live, whose, password) } : undefined}
        settings={settings}
        surface={surface}
        preferences={preferences}
      />
    ) : (
      <App createConnection={createConnection} settings={settings} surface={surface} embedded={query.has('embed')} preferences={preferences} beside={query.has('beside')} where={whereOfTheChat} />
    )}
  </StrictMode>,
);
