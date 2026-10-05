// The desktop app (spec 14.3): one window with the agent's browser on the left and the chat on the
// right. The browser is this app's own Chromium. The agent's core runs beside the app as its own
// process and drives that browser by attaching to it; the chat is the session's viewer.

'use strict';

const { app, BrowserWindow, WebContentsView, ipcMain, session, shell } = require('electron');
const { spawn, spawnSync } = require('node:child_process');
const crypto = require('node:crypto');
const path = require('node:path');
const readline = require('node:readline');

const { viewerOf, errorOf, chatAddress, placeable } = require('./core-line.cjs');

// The core finds the page it is to drive by this mark in the page's address.
const AGENT_MARK = '#bap-agent';
const REPOSITORY = path.join(__dirname, '..', '..');
// The core attaches through this app's debugging port, which listens on this machine only. The
// port is taken from a range of its own, afresh each time the app starts, unless one is named.
const DEBUG_PORT = Number(process.env.BAP_DESKTOP_DEBUG_PORT) || 19200 + crypto.randomInt(700);
// The pages of the demo site the shell may open in the agent's browser.
const DEMO_PAGES = { start: 'start.html', checkin: 'checkin.html', signup: 'signup.html' };
const CORNER = 12;

app.commandLine.appendSwitch('remote-debugging-port', String(DEBUG_PORT));

let win = null;
let agentView = null;
let chatView = null;
let core = null;
/** Where the core's service is, once it has said so. */
let service = '';
let lastError = '';

const state = {
  /** starting: the core is coming up. running: the chat is live. stopped: the core is gone. */
  core: 'starting',
  message: '',
  address: '',
  canGoBack: false,
  canGoForward: false,
};

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
    // The core is a command that starts another: both go, and whatever they started.
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
  chatView.setVisible(false);
  tellShell();

  core = spawn('uv', ['run', '--project', REPOSITORY, 'bap-browser', 'agent', '--chat'], {
    // The project's folder, where the file with the model's key is.
    cwd: REPOSITORY,
    env: {
      ...process.env,
      // A token of this run's own, so that the app knows the chat's address without being told it.
      BAP_BROWSER_TOKEN: crypto.randomBytes(24).toString('base64url'),
      BAP_BROWSER__BROWSER__CDP_URL: `http://127.0.0.1:${DEBUG_PORT}`,
      BAP_BROWSER__BROWSER__CDP_TARGET: AGENT_MARK,
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
    state.core = 'running';
    chatView.webContents.loadURL(chatAddress(viewer));
    chatView.setVisible(true);
    agentView.webContents.loadURL(`${service}/demo-site/${DEMO_PAGES.start}`);
    tellShell();
  });
  core.on('exit', (code) => {
    core = null;
    state.core = 'stopped';
    state.message = lastError || `The agent's core stopped (code ${code}).`;
    chatView.setVisible(false);
    tellShell();
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1000,
    minHeight: 640,
    title: 'BAP Browser',
    backgroundColor: '#ffffff',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.setMenuBarVisibility(false);
  // The shell is one page from this app's own files, and stays that.
  win.webContents.on('will-navigate', (event) => event.preventDefault());
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  // The agent's browser keeps its sign-ins between runs, apart from everything else in the app.
  const agentSession = session.fromPartition('persist:agent');
  // A page the agent visits is given nothing it asks the person's machine for.
  agentSession.setPermissionRequestHandler((_contents, _permission, answer) => answer(false));
  agentView = new WebContentsView({ webPreferences: { session: agentSession, sandbox: true, contextIsolation: true, nodeIntegration: false } });
  chatView = new WebContentsView({ webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false } });
  for (const view of [agentView, chatView]) {
    view.setBorderRadius(CORNER);
    win.contentView.addChildView(view);
  }
  chatView.setVisible(false);
  // A view that has loaded nothing does not answer a debugger, and whoever attaches to the app's
  // browser would wait for it for ever. It is given an empty page from the start.
  chatView.webContents.loadURL('about:blank');

  const page = agentView.webContents;
  // A page that opens a new window gets it in the same place: the agent drives one page.
  page.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) page.loadURL(url);
    return { action: 'deny' };
  });
  for (const event of ['did-navigate', 'did-navigate-in-page', 'did-finish-load']) page.on(event, tellShell);
  // A link in the agent's answer opens in the person's own browser, not over the chat.
  chatView.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });

  // The core is started once the marked page is there for it to find.
  page.once('did-finish-load', startCore);
  page.loadURL(`about:blank${AGENT_MARK}`);
  win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  win.on('closed', () => {
    win = null;
  });
}

/** Only the app's own shell may ask for anything. */
const fromShell = (event) => win !== null && event.sender === win.webContents;

ipcMain.on('ready', (event) => {
  if (fromShell(event)) tellShell();
});

ipcMain.on('place', (event, rects) => {
  if (!fromShell(event) || typeof rects !== 'object' || rects === null) return;
  agentView.setBounds(placeable(rects.agent));
  chatView.setBounds(placeable(rects.chat));
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
  // The core looks for the marked page again.
  agentView.webContents.once('did-finish-load', startCore);
  agentView.webContents.loadURL(`about:blank${AGENT_MARK}`);
});

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());
app.on('quit', stopCore);
