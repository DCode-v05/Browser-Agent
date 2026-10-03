import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App, preferencesFrom } from './App';
import { socketAddress, takeToken } from './connection/address';
import type { Connection } from './connection/connection';
import { DemoConnection } from './connection/demo';
import { SocketConnection } from './connection/socket';
import { SESSIONS, STATES } from './demo/sessions';
import { createDemoSettings } from './demo/settings';
import type { Surface } from './protocol';
import './tokens.css';
import './styles/base.css';
import './styles/app.css';
import './styles/settings.css';

const HEARTBEAT_MS = 2000;
/** What the viewer keeps by itself. The rest of the settings arrive with the settings API (spec 10.2). */
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

function createConnection(): Connection {
  if (recorded) return new DemoConnection(recording, { pace, heartbeatMs: HEARTBEAT_MS });
  if (token) return new SocketConnection({ url: socketAddress(location.href, query.get('session') ?? 'default'), token });
  // Opened without its token: there is no session this page may show.
  return { start: (handlers) => handlers.onStatus('refused'), send: () => undefined, now: () => Date.now() / 1000, close: () => undefined };
}

const settings = recorded ? createDemoSettings() : createDemoSettings(KEPT_BY_THE_VIEWER);

const preferences = preferencesFrom(await settings.load(surface));
const theme = query.get('theme');
if (theme === 'light' || theme === 'dark') preferences.colourMode = theme;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App createConnection={createConnection} settings={settings} surface={surface} embedded={query.has('embed')} preferences={preferences} />
  </StrictMode>,
);
