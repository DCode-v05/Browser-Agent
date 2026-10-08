import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App } from './App';
import { preferencesFrom } from './preferences';
import { authFrom, type AuthState, type Role } from './auth/api';
import { SignIn } from './auth/SignIn';
import { Studio } from './Studio';
import { desktopOpener, factsFrom, NO_FACTS, roomsFrom } from './studio/rooms';
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
/** The token of a visit someone signed in for, kept for the life of the tab (spec 4.11). */
const VISIT_KEY = 'bap-browser.visit';
/** The service's own token, as the address module keeps it. */
const OPERATOR_KEY = 'bap-browser.token';
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
      // A tab that can keep nothing still works until it is reloaded.
    }
  },
  removeItem: (key: string) => {
    try {
      sessionStorage.removeItem(key);
    } catch {
      // Nothing was kept.
    }
  },
};
// The admin's page is at /admin, and everyone else's at the address above it (spec 4.11).
const atAdmin = /\/admin\/?$/.test(location.pathname);
const adminPage = atAdmin ? location.pathname : new URL('admin', location.href).pathname;
const userPage = atAdmin ? new URL('./', location.href).pathname : location.pathname;

// The service's own token arrives in the address, with the link the service printed when it started.
const operator = recorded ? null : takeToken(location, tabStorage, (address) => history.replaceState(null, '', address));
const visit = recorded ? null : tabStorage.getItem(VISIT_KEY);
// A visit someone signed in for comes before the service's own token.
let token = visit ?? operator;
let role: Role = 'admin';
/** The service has people sign in. Without that, its own token is the one way in. */
let signsIn = false;
let signInPage: { role: Role; state: AuthState } | null = null;

// A link opened in a tab that already shows the viewer changes only what follows the #, and the
// browser does not load the page again by itself. Loading it again takes the new token in.
if (!recorded) {
  window.addEventListener('hashchange', () => {
    if (new URLSearchParams(location.hash.slice(1)).get('token')) location.reload();
  });
}

const auth = authFrom(location.href);
if (!recorded) {
  let known = await auth.state(token);
  if (known && known !== 'no_accounts' && known.role === null && visit && operator) {
    // The visit has run out. The service's own link, where the page was opened with it, still holds.
    tabStorage.removeItem(VISIT_KEY);
    token = operator;
    known = await auth.state(token);
  }
  if (known && known !== 'no_accounts') {
    signsIn = true;
    // The first time, the admin's page makes the admin's password with the service's own link.
    const firstTime = atAdmin && known.operator && !known.admin_set;
    // Nobody is signed in; or a user is, on the admin's page.
    const mustSignIn = known.role === null || (atAdmin && known.role !== 'admin');
    if (firstTime || mustSignIn) signInPage = { role: atAdmin ? 'admin' : 'user', state: known };
    else role = known.role ?? 'admin';
  } else if (known === 'no_accounts') {
    token = operator;
  }
}

function signedIn(visitToken: string) {
  tabStorage.setItem(VISIT_KEY, visitToken);
  // From here on the person is who they signed in as, not whoever held the service's link.
  tabStorage.removeItem(OPERATOR_KEY);
  location.reload();
}

async function signOut() {
  if (token) await auth.signOut(token);
  tabStorage.removeItem(VISIT_KEY);
  tabStorage.removeItem(OPERATOR_KEY);
  tabStorage.removeItem(PAGE_KEY);
  location.assign(role === 'admin' ? adminPage : userPage);
}

let ended = false;
/** The visit is over: signed out on another page, a new password, or its time is up. The page asks again. */
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
  // Opened without its token: there is no session this page may show.
  return { start: (handlers) => handlers.onStatus('refused'), send: () => undefined, now: () => Date.now() / 1000, close: () => undefined };
}

const live = !recorded && !signInPage && token ? token : null;

// What the service has, asked once: the window then asks for nothing the service does not have.
const facts = live ? await factsFrom(location.href, live) : NO_FACTS;

// A live session's settings are the service's. A recorded one plays with settings of its own, and a
// service that has none to give leaves the viewer the two that are the viewer's.
let settings: SettingsSource = recorded ? createDemoSettings() : live && facts.settings ? settingsFrom(location.href, live) : createDemoSettings(KEPT_BY_THE_VIEWER);
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
const loadRooms = live && !query.has('session') ? roomsFrom(location.href, live, signsIn && live === visit ? visitEnded : undefined) : null;
const rooms = loadRooms ? facts.rooms : null;
const openDesktop = rooms && live && facts.desktop ? desktopOpener(location.href, live) : undefined;
const systems = rooms && live && facts.systems ? systemsFrom(location.href, live, W.systems.unreachable) : undefined;
// Who is signed in, and what they may use and see.
const me: Me | null = systems && signsIn ? await systems.me() : null;

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
        systems={systems}
        role={role}
        me={me}
        onSignOut={signsIn ? () => void signOut() : undefined}
        passwords={signsIn && role === 'admin' && live ? { set: (whose, password) => auth.setPassword(live, whose, password) } : undefined}
        settings={settings}
        surface={surface}
        preferences={preferences}
      />
    ) : (
      <App createConnection={createConnection} settings={settings} surface={surface} embedded={query.has('embed')} preferences={preferences} />
    )}
  </StrictMode>,
);
