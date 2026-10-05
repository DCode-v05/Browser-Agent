// The side panel. It does three things:
//  1. shows the session's viewer, which is the chat;
//  2. passes on to the pages of this window what the viewer says about who is driving, so that each
//     page can show it (look.js);
//  3. for take-over Chrome, is the bridge (spec 4.9): it dials out to the agent's core, attaches to
//     one tab of this browser, and carries the core's commands to that tab and the tab's events back.
// The bridge lives here and not in the background, because a page that stays open keeps its
// connection, and the panel is open for as long as the person is working with the agent.

const SESSION_FILE = 'session.json';
const LOOK = 'bap-browser.look';
// How often the session file is read again, and how often the pages are told again. A page that has
// just loaded learns within that time who is driving.
const RELOAD_MS = 2000;
const RETELL_MS = 1000;
// How long a new tab is given to load before the browser lets a debugger attach to it.
const TAB_READY_MS = 5000;
const GROUP = { title: 'BAP agent', color: 'purple' };

const frame = document.getElementById('viewer');
const waiting = document.getElementById('waiting');
const connecting = document.getElementById('connecting');

/** The viewer's address now shown, and its origin: only messages from there are passed on. */
let shown = '';
let origin = '';
/** What the viewer said last about who is driving. */
let look = null;

/** The bridge: where it dials in, its connection, and the tab it is attached to. */
let bridgeAt = '';
let bridge = null;
let agentTab = null;

async function connect() {
  let session = {};
  try {
    // The core writes this file when a session starts and removes it when the session ends.
    const answer = await fetch(chrome.runtime.getURL(SESSION_FILE), { cache: 'no-store' });
    session = answer.ok ? await answer.json() : {};
  } catch {
    session = {};
  }
  showViewer(typeof session.viewer === 'string' ? session.viewer : '');
  dial(typeof session.bridge === 'string' ? session.bridge : '', session.token);
  frame.hidden = !shown;
  connecting.hidden = Boolean(shown) || !bridgeAt;
  waiting.hidden = Boolean(shown) || Boolean(bridgeAt);
}

function showViewer(viewer) {
  if (viewer === shown) return;
  shown = viewer;
  look = null;
  if (viewer) {
    origin = new URL(viewer).origin;
    frame.src = viewer;
  } else {
    origin = '';
    frame.removeAttribute('src');
    tell({ type: LOOK, tone: 'none' });
  }
}

async function tell(message) {
  const tabs = await chrome.tabs.query({ currentWindow: true });
  for (const tab of tabs) {
    // A tab with no page of ours in it (the browser's own pages) has nobody to answer.
    chrome.tabs.sendMessage(tab.id, message).catch(() => undefined);
  }
}

window.addEventListener('message', (event) => {
  if (event.source !== frame.contentWindow || event.origin !== origin) return;
  if (typeof event.data !== 'object' || event.data === null || event.data.type !== LOOK) return;
  look = event.data;
  tell(look);
});

// The bridge.

function dial(address, token) {
  if (address === bridgeAt) return;
  bridgeAt = address;
  bridge?.close();
  bridge = null;
  if (!address || typeof token !== 'string') return;
  const socket = new WebSocket(address);
  bridge = socket;
  socket.onopen = () => socket.send(JSON.stringify({ type: 'auth', token }));
  socket.onmessage = (message) => answer(socket, message.data);
  socket.onclose = () => {
    if (bridge !== socket) return;
    // The session file is read again in a moment, and the bridge dials again if the core is still there.
    bridge = null;
    bridgeAt = '';
    letGo();
  };
}

async function answer(socket, data) {
  let asked;
  try {
    asked = JSON.parse(data);
  } catch {
    return;
  }
  const reply = { id: asked.id };
  try {
    reply.result = await carryOut(asked.method, asked.params ?? {});
  } catch (error) {
    reply.error = error instanceof Error ? error.message : String(error);
  }
  if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(reply));
}

async function carryOut(method, params) {
  if (method === 'attachToTab') return { targetInfo: await attach() };
  if (method === 'detachFromTab') return letGo();
  if (method === 'forwardCDPCommand') {
    if (agentTab === null) throw new Error("The agent's tab is not attached.");
    const target = params.sessionId ? { tabId: agentTab, sessionId: params.sessionId } : { tabId: agentTab };
    return (await chrome.debugger.sendCommand(target, params.method, params.params)) ?? {};
  }
  throw new Error(`The bridge does not know "${method}".`);
}

/** Opens the agent's own tab, in a group of its own, and attaches to it. */
async function attach() {
  await letGo();
  const tab = await chrome.tabs.create({ url: 'about:blank', active: true });
  try {
    const group = await chrome.tabs.group({ tabIds: tab.id });
    await chrome.tabGroups.update(group, GROUP);
  } catch {
    // A browser with no tab strip has no groups. The tab is the agent's all the same.
  }
  const until = Date.now() + TAB_READY_MS;
  while ((await chrome.tabs.get(tab.id)).status !== 'complete' && Date.now() < until) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  await chrome.debugger.attach({ tabId: tab.id }, '1.3');
  agentTab = tab.id;
  return (await chrome.debugger.sendCommand({ tabId: tab.id }, 'Target.getTargetInfo')).targetInfo;
}

/** Stops driving the agent's tab. The tab stays open, where the agent left it. */
async function letGo() {
  if (agentTab === null) return {};
  const tab = agentTab;
  agentTab = null;
  await chrome.debugger.detach({ tabId: tab }).catch(() => undefined);
  return {};
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (source.tabId !== agentTab || bridge?.readyState !== WebSocket.OPEN) return;
  bridge.send(JSON.stringify({ method: 'forwardCDPEvent', params: { sessionId: source.sessionId, method, params } }));
});

// The person closed the tab, or told the browser to stop the debugging: the agent has lost its tab.
chrome.debugger.onDetach.addListener((source) => {
  if (source.tabId !== agentTab) return;
  agentTab = null;
  if (bridge?.readyState === WebSocket.OPEN) bridge.send(JSON.stringify({ method: 'detached' }));
});

setInterval(connect, RELOAD_MS);
setInterval(() => look && tell(look), RETELL_MS);
connect();
