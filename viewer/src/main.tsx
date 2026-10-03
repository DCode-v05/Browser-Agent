import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import { App, preferencesFrom } from './App';
import { DemoConnection } from './connection/demo';
import { SESSIONS, STATES } from './demo/sessions';
import { createDemoSettings } from './demo/settings';
import type { Surface } from './protocol';
import './tokens.css';
import './styles/base.css';
import './styles/app.css';
import './styles/settings.css';

const HEARTBEAT_MS = 2000;

const query = new URLSearchParams(location.search);
const named = query.get('surface');
const surface: Surface = named === 'mobile' || named === 'desktop' ? named : 'web';
// The live service arrives with slice 4. Until then the viewer plays recorded sessions.
const state = query.get('state');
const recording = (state && STATES[state]) || SESSIONS[query.get('demo') ?? 'signup'] || SESSIONS.signup;
const pace = state ? 0 : Number(query.get('pace') ?? 1);

const settings = createDemoSettings();
const createConnection = () => new DemoConnection(recording, { pace, heartbeatMs: HEARTBEAT_MS });

const preferences = preferencesFrom(await settings.load(surface));
const theme = query.get('theme');
if (theme === 'light' || theme === 'dark') preferences.colourMode = theme;

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App createConnection={createConnection} settings={settings} surface={surface} embedded={query.has('embed')} preferences={preferences} />
  </StrictMode>,
);
