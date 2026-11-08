'use strict';

const { app, BrowserWindow, WebContentsView, ipcMain, nativeTheme, session, shell } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const crypto = require('node:crypto');
const path = require('node:path');
const readline = require('node:readline');

const { viewerOf, errorOf, chatAddress, placeable, coreArguments, around, sessionsUp } = require('./core-line.cjs');

const AGENT_MARK = '#bap-agent';
const REPOSITORY = path.join(__dirname, '..', '..');
const DEBUG_PORT = Number(process.env.BAP_DESKTOP_DEBUG_PORT) || 19200 + crypto.randomInt(700);
const DEMO_PAGES = { start: 'start.html', checkin: 'checkin.html', signup: 'signup.html' };
const CORNER = 12;
const OVERLAY_HEIGHT = 36;
const overlayOf = (dark) => ({ color: dark ? '#1E1E1E' : '#F5F4F2', symbolColor: dark ? '#E9EBDF' : '#1A1714', height: OVERLAY_HEIGHT });
const paneBackgroundOf = (dark) => (dark ? '#1E1E1E' : '#F5F4F2');
const PAGES = ['builtin', 'computer'];
const PAGES_WAIT_MS = 90000;
const PAGES_POLL_MS = 500;

app.commandLine.appendSwitch('remote-debugging-port', String(DEBUG_PORT));

let win = null;
let agentView = null;
let chatView = null;
let computerView = null;
let core = null;
let service = '';
let lastError = '';

const state = {
  core: 'starting',
  message: '',
  address: '',
  canGoBack: false,
  canGoForward: false,
  page: 'browser',
};

function showPage() {
  const running = state.core === 'running';
  agentView.setVisible(state.page === 'browser');
  chatView.setVisible(running && state.page === 'browser');
  computerView.setVisible(running && state.page === 'computer');
}

function tellShell() {
  if (!win || win.isDestroyed()) return;
  const page = agentView.webContents;
  state.address = page.getURL().replace(AGENT_MARK, '');
  state.canGoBack = page.navigationHistory.canGoBack();
  state.canGoForward = page.navigationHistory.canGoForward();
  win.webContents.send('state', { ...state });
}

function stopCore() {
  if (!core) return;
  const running = core;
  core = null;
  running.removeAllListeners('exit');
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(running.pid), '/T', '/F']);
  } else {
    running.kill('SIGTERM');
  }
}

function startCore() {
  service = '';
  lastError = '';
  state.core = 'starting';
  state.message = '';
  showPage();
  tellShell();

  core = spawn('uv', coreArguments(REPOSITORY), {
    cwd: REPOSITORY,
    env: {
      ...process.env,
      BAP_BROWSER_TOKEN: crypto.randomBytes(24).toString('base64url'),
      BAP_BROWSER__BROWSER__CDP_URL: `http://127.0.0.1:${DEBUG_PORT}`,
      BAP_BROWSER__BROWSER__CDP_TARGET: AGENT_MARK,
      BAP_BROWSER_DESKTOP_APP_CORE: '1',
    },
    stdio: ['ignore', 'ignore', 'pipe'],
    windowsHide: true,
  });
  core.on('error', (error) => {
    lastError = `The agent's core could not be started: ${error.message}`;
  });
  readline.createInterface({ input: core.stderr }).on('line', (line) => {
    lastError = errorOf(line) ?? lastError;
    const viewer = viewerOf(line);
    if (!viewer || service) return;
    service = viewer.origin;
    agentView.webContents.loadURL(`about:blank${AGENT_MARK}`);
    void showWhenReady(viewer);
  });
  core.on('exit', (code) => {
    core = null;
    state.core = 'stopped';
    state.message = lastError || `The agent's core stopped (code ${code}).`;
    showPage();
    tellShell();
  });
}

async function showWhenReady(viewer) {
  const ends = Date.now() + PAGES_WAIT_MS;
  while (core && Date.now() < ends) {
    try {
      const answer = await fetch(`${viewer.origin}/api/sessions`, { headers: { Authorization: `Bearer ${viewer.token}` } });
      if (answer.ok && sessionsUp(await answer.json(), PAGES)) break;
    } catch {
    }
    await new Promise((resolve) => setTimeout(resolve, PAGES_POLL_MS));
  }
  if (!core) return;
  state.core = 'running';
  chatView.webContents.loadURL(chatAddress(viewer, 'builtin'));
  computerView.webContents.loadURL(chatAddress(viewer, 'computer'));
  showPage();
  tellShell();
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1000,
    minHeight: 640,
    title: 'BAP Browser',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#151515' : '#ffffff',
    frame: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'hidden',
    ...(process.platform === 'darwin' ? {} : { titleBarOverlay: overlayOf(nativeTheme.shouldUseDarkColors) }),
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.setMenuBarVisibility(false);
  win.webContents.on('will-navigate', (event) => event.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  const agentSession = session.fromPartition('persist:agent');
  agentSession.setPermissionRequestHandler((_contents, _permission, answer) => answer(false));
  const paneBackground = paneBackgroundOf(nativeTheme.shouldUseDarkColors);
  agentView = new WebContentsView({ backgroundColor: paneBackground, webPreferences: { session: agentSession, sandbox: true, contextIsolation: true, nodeIntegration: false } });
  chatView = new WebContentsView({ backgroundColor: paneBackground, webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  computerView = new WebContentsView({ backgroundColor: paneBackground, webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  for (const view of [agentView, chatView, computerView]) {
    view.setBorderRadius(CORNER);
    win.contentView.addChildView(view);
  }
  for (const view of [chatView, computerView]) {
    view.setVisible(false);
    view.webContents.loadURL('about:blank');
  }

  const page = agentView.webContents;
  page.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) page.loadURL(url);
    return { action: 'deny' };
  });
  for (const event of ['did-navigate', 'did-navigate-in-page', 'did-finish-load']) page.on(event, tellShell);
  for (const view of [chatView, computerView]) {
    view.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:/.test(url)) shell.openExternal(url);
      return { action: 'deny' };
    });
  }

  page.once('did-finish-load', startCore);
  page.loadURL(`about:blank${AGENT_MARK}`);
  win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  win.on('closed', () => {
    win = null;
  });
}

const fromShell = (event) => win !== null && event.sender === win.webContents;

ipcMain.on('ready', (event) => {
  if (fromShell(event)) tellShell();
});

ipcMain.on('place', (event, rects) => {
  if (!fromShell(event) || typeof rects !== 'object' || rects === null) return;
  agentView.setBounds(placeable(rects.agent));
  chatView.setBounds(placeable(rects.chat));
  computerView.setBounds(placeable(around(placeable(rects.agent), placeable(rects.chat))));
});

ipcMain.on('theme', (event, dark) => {
  if (!fromShell(event) || typeof dark !== 'boolean') return;
  if (process.platform !== 'darwin') win?.setTitleBarOverlay(overlayOf(dark));
  const paneBackground = paneBackgroundOf(dark);
  for (const view of [agentView, chatView, computerView]) view?.setBackgroundColor(paneBackground);
});

ipcMain.on('show', (event, page) => {
  if (!fromShell(event) || (page !== 'browser' && page !== 'computer')) return;
  state.page = page;
  showPage();
  tellShell();
});

ipcMain.on('go', (event, action, name) => {
  if (!fromShell(event)) return;
  const page = agentView.webContents;
  if (action === 'back' && page.navigationHistory.canGoBack()) page.navigationHistory.goBack();
  else if (action === 'forward' && page.navigationHistory.canGoForward()) page.navigationHistory.goForward();
  else if (action === 'reload') page.reload();
  else if (action === 'open' && service && Object.hasOwn(DEMO_PAGES, name)) page.loadURL(`${service}/demo-site/${DEMO_PAGES[name]}`);
});

ipcMain.on('start-again', (event) => {
  if (!fromShell(event) || state.core !== 'stopped') return;
  agentView.webContents.once('did-finish-load', startCore);
  agentView.webContents.loadURL(`about:blank${AGENT_MARK}`);
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('quit', stopCore);
