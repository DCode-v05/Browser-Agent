// The background of the extension. For take-over Chrome it is the bridge (spec 4.9): it dials out to
// the agent's core, attaches to one tab of this browser, carries the core's commands to that tab and
// the tab's events back, and decides which sites the agent may read and act on (spec 8.8).
//
// It lives here and not in the side panel, so that closing the panel does not end the agent's work.
// The connection keeps this worker awake: the bridge says that it is alive at a steady pace.

const SESSION_FILE = 'session.json';
const PANEL = 'panel.html';
const GROUP = { title: 'BAP agent', color: 'purple' };
// How long a new tab is given to load before the browser lets a debugger attach to it.
const TAB_READY_MS = 5000;
// How long the bridge waits before it dials again, growing with each try that fails.
const RETRY_FIRST_MS = 500;
const RETRY_MOST_MS = 30000;
// While no session is known, the session file is looked at again this often even with no panel open.
const LOOK_AGAIN_MINUTES = 0.5;
// The size of the window that asks the person, when no panel is open to ask them in.
const QUESTION_WINDOW = { width: 420, height: 320 };

// Close codes of the core (service/app.py).
const REFUSED = 4401;

// What the browser never lets an agent touch, whatever anyone allows: its own pages, other
// extensions and the extension store.
const STORE_HOSTS = new Set(['chromewebstore.google.com', 'microsoftedge.microsoft.com']);
const WEB = new Set(['http:', 'https:']);
const NO_SITE = new Set(['', 'about:blank', 'about:srcdoc']);

// The commands that act on a page or take it elsewhere, and the ones that read it.
const NAVIGATES = new Set(['Page.navigate', 'Page.reload', 'Page.navigateToHistoryEntry']);
const READS = /^(Runtime\.(evaluate|callFunctionOn)|Page\.captureScreenshot|DOM\.|DOMSnapshot\.|Accessibility\.)/;

/** What is kept across a restart of this worker, for as long as the browser runs. */
const kept = { key: null, dialled: '', agentTab: null, stopped: false };
/** What the core said when it let the bridge in: the pace of the heartbeat, and the person's limits. */
let rules = null;
let socket = null;
let session = {};
let tries = 0;
let heard = 0;
let beat = null;
let dialAgain = null;
/** The question the person is being asked now, and who is waiting for the answer. */
let question = null;
let answered = null;
let questions = 0;
/** A site the person allowed once: for the call that asked, and no longer than one operation takes. */
let once = null;

const ready = (async () => {
  const stored = await chrome.storage.session.get(Object.keys(kept));
  Object.assign(kept, stored);
})();

const keep = () => chrome.storage.session.set(kept);

// Finding the session, and dialling in.

async function check() {
  await ready;
  try {
    // The core writes this file when a session starts and removes it when the session ends.
    const answer = await fetch(chrome.runtime.getURL(SESSION_FILE), { cache: 'no-store' });
    session = answer.ok ? await answer.json() : {};
  } catch {
    session = {};
  }
  const address = typeof session.bridge === 'string' ? session.bridge : '';
  if (address !== kept.dialled) {
    // Another session, or none: what belonged to the last one is let go.
    hangUp();
    await letGo();
    Object.assign(kept, { key: null, dialled: address, stopped: false });
    await keep();
  }
  if (address && !socket && !kept.stopped) dial(address);
  return state();
}

function state() {
  return {
    viewer: typeof session.viewer === 'string' ? session.viewer : '',
    wanted: Boolean(kept.dialled),
    connected: Boolean(socket && rules && socket.readyState === WebSocket.OPEN),
    stopped: kept.stopped,
    attached: kept.agentTab !== null,
    question,
  };
}

function dial(address) {
  clearTimeout(dialAgain);
  const dialling = new WebSocket(address);
  socket = dialling;
  rules = null;
  dialling.onopen = () => {
    // The key lets a bridge that was let in come back after a cut. Without one, the pairing token
    // of the session file lets it in once.
    const how = kept.key ? { key: kept.key } : { token: session.token };
    dialling.send(JSON.stringify({ type: 'auth', attached: kept.agentTab !== null, ...how }));
  };
  dialling.onmessage = (message) => hear(dialling, message.data);
  dialling.onclose = (closed) => {
    if (socket !== dialling) return;
    socket = null;
    rules = null;
    clearInterval(beat);
    if (closed.code === REFUSED) {
      // The key is not taken any more: the session file has a pairing token when the core wants one.
      kept.key = null;
      keep();
    }
    announce();
    if (kept.stopped || !kept.dialled) return;
    // It dials again by itself, a little later each time (spec 4.9).
    const wait = Math.min(RETRY_MOST_MS, RETRY_FIRST_MS * 2 ** tries);
    tries += 1;
    dialAgain = setTimeout(check, wait);
  };
}

function hangUp() {
  clearTimeout(dialAgain);
  clearInterval(beat);
  const open = socket;
  socket = null;
  rules = null;
  open?.close();
  settle('deny');
}

async function hear(from, data) {
  heard = Date.now();
  let said;
  try {
    said = JSON.parse(data);
  } catch {
    return;
  }
  if (said.type === 'paired') {
    rules = said;
    tries = 0;
    kept.key = said.key;
    await keep();
    clearInterval(beat);
    beat = setInterval(() => {
      // A channel that has fallen silent is closed, and dialled again.
      if (Date.now() - heard > said.dead_after_s * 1000) return from.close();
      if (from.readyState === WebSocket.OPEN) from.send('{"type":"ping"}');
    }, said.heartbeat_s * 1000);
    announce();
    return;
  }
  if (said.type === 'pong' || typeof said.id !== 'number') return;
  const reply = { id: said.id };
  try {
    reply.result = await carryOut(said.method, said.params ?? {});
  } catch (error) {
    reply.error = error instanceof Error ? error.message : String(error);
  }
  if (from.readyState === WebSocket.OPEN) from.send(JSON.stringify(reply));
}

async function carryOut(method, params) {
  if (method === 'attachToTab') return { targetInfo: await attach() };
  if (method === 'detachFromTab') return letGo();
  if (method === 'permit') return permit(params);
  if (method === 'permitDone') {
    // The call that was allowed once has finished.
    once = null;
    return {};
  }
  if (method === 'forwardCDPCommand') {
    if (kept.agentTab === null) throw new Error("The agent's tab is not attached.");
    await enforce(params.method, params.params ?? {});
    const target = params.sessionId ? { tabId: kept.agentTab, sessionId: params.sessionId } : { tabId: kept.agentTab };
    return (await chrome.debugger.sendCommand(target, params.method, params.params)) ?? {};
  }
  throw new Error(`The bridge does not know "${method}".`);
}

// The agent's tab.

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
  kept.agentTab = tab.id;
  await keep();
  announce();
  return (await chrome.debugger.sendCommand({ tabId: tab.id }, 'Target.getTargetInfo')).targetInfo;
}

/** Stops driving the agent's tab. The tab stays open, where the agent left it. */
async function letGo() {
  if (kept.agentTab === null) return {};
  const tab = kept.agentTab;
  kept.agentTab = null;
  await keep();
  await chrome.debugger.detach({ tabId: tab }).catch(() => undefined);
  announce();
  return {};
}

chrome.debugger.onEvent.addListener((source, method, params) => {
  if (source.tabId !== kept.agentTab || socket?.readyState !== WebSocket.OPEN) return;
  socket.send(JSON.stringify({ method: 'forwardCDPEvent', params: { sessionId: source.sessionId, method, params } }));
});

// The person closed the tab, or told the browser to stop the debugging: the agent has lost its tab.
chrome.debugger.onDetach.addListener(async (source) => {
  await ready;
  if (source.tabId !== kept.agentTab) return;
  kept.agentTab = null;
  await keep();
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ method: 'detached' }));
  announce();
});

// Which sites the agent may read and act on (spec 8.8). The core asks before each call, and every
// command that acts on the tab is checked here again: the core's word is not relied on.

/** What an address is to these rules: no site at all, a site that is never offered, or a site by name. */
function siteOf(address) {
  if (NO_SITE.has(address ?? '')) return { free: true };
  let url;
  try {
    url = new URL(address);
  } catch {
    return { never: true, name: 'this page' };
  }
  // The agent's own start page comes from the core itself.
  if (rules?.own_address && url.origin === rules.own_address) return { free: true };
  if (!WEB.has(url.protocol) || STORE_HOSTS.has(url.hostname)) return { never: true, name: url.hostname || url.protocol };
  if (url.hostname === 'chrome.google.com' && url.pathname.startsWith('/webstore')) return { never: true, name: url.hostname };
  return { name: url.hostname };
}

const covers = (listed, name) => name === listed || name.endsWith('.' + listed);

/** What the person, or the deployment, has decided for a site: allow, block or ask. */
async function decided(site) {
  if (site.never) return 'block';
  if ((rules?.blocked_sites ?? []).some((listed) => covers(listed, site.name))) return 'block';
  const { sites = {} } = await chrome.storage.local.get('sites');
  return sites[site.name] ?? rules?.default_site_permission ?? 'ask';
}

const allowedOnce = (site) => Boolean(once && once.name === site.name && Date.now() < once.until);

const refusal = (site) => `The person has not allowed actions on ${site.name}.`;

async function permit({ kind, url, summary }) {
  once = null;
  const site = siteOf(url);
  if (site.free) return { allowed: true };
  const choice = await decided(site);
  if (choice === 'block') return { allowed: false, reason: 'blocked', site: site.name };
  const everyAct = rules?.mode === 'ask_before_acting' && kind === 'act';
  if (choice === 'allow' && !everyAct) return { allowed: true };
  // A site that is already allowed is not offered "always" again.
  const said = await ask({ site: site.name, summary: String(summary ?? ''), kind, always: choice !== 'allow' });
  if (said === 'always') {
    const { sites = {} } = await chrome.storage.local.get('sites');
    await chrome.storage.local.set({ sites: { ...sites, [site.name]: 'allow' } });
    return { allowed: true };
  }
  if (said === 'once') {
    once = { name: site.name, until: Date.now() + (rules?.op_timeout_ms ?? 0) };
    return { allowed: true };
  }
  return { allowed: false, reason: said === 'timeout' ? 'timeout' : 'denied', site: site.name };
}

async function enforce(method, params) {
  const acts = method.startsWith('Input.') || NAVIGATES.has(method);
  if (!acts && !READS.test(method)) return;
  if (method === 'Page.navigate') {
    const to = siteOf(params.url);
    if (to.free) return;
    const choice = await decided(to);
    if (choice === 'block' || (choice !== 'allow' && !allowedOnce(to))) throw new Error(refusal(to));
    return;
  }
  const here = siteOf((await chrome.tabs.get(kept.agentTab)).url);
  if (here.free) return;
  const choice = await decided(here);
  // On a blocked site nothing is read and nothing is done. On a site not yet decided on, nothing is
  // done unless the person has just allowed it.
  if (choice === 'block' || (acts && choice !== 'allow' && !allowedOnce(here))) throw new Error(refusal(here));
}

// Asking the person. The question is shown by this extension's own page, never inside a web page,
// which could press the buttons itself.

async function ask(asked) {
  settle('deny');
  questions += 1;
  question = { id: questions, ...asked };
  const waiting = new Promise((resolve) => {
    answered = resolve;
  });
  const seconds = rules?.preview_timeout_s ?? 0;
  const timer = setTimeout(() => settle('timeout'), seconds * 1000);
  const shown = await chrome.runtime.getContexts({ contextTypes: ['SIDE_PANEL', 'TAB', 'POPUP'] });
  if (!shown.some((context) => context.documentUrl?.includes(PANEL))) {
    await chrome.windows.create({ url: chrome.runtime.getURL(PANEL), type: 'popup', ...QUESTION_WINDOW }).catch(() => undefined);
  }
  announce();
  const said = await waiting;
  clearTimeout(timer);
  return said;
}

function settle(said) {
  const resolve = answered;
  question = null;
  answered = null;
  resolve?.(said);
  announce();
}

/** Tells the extension's own pages that something changed. */
function announce() {
  chrome.runtime.sendMessage({ type: 'bap.state', state: state() }).catch(() => undefined);
}

// What the extension's own pages ask of the background.

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (sender.id !== chrome.runtime.id || typeof message !== 'object' || message === null) return false;
  if (message.type === 'bap.check') {
    check().then(respond);
    return true;
  }
  if (message.type === 'bap.answer' && question && message.id === question.id) {
    settle(['once', 'always'].includes(message.choice) ? message.choice : 'deny');
  } else if (message.type === 'bap.stop') {
    // The person's own Stop: the agent is off every tab at once, whatever the core is doing.
    kept.stopped = true;
    keep().then(letGo).then(hangUp).then(announce);
  }
  return false;
});

// The extension's icon opens the chat in the side panel.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);

chrome.alarms.create('look-again', { periodInMinutes: LOOK_AGAIN_MINUTES });
chrome.alarms.onAlarm.addListener(() => check());
chrome.runtime.onStartup.addListener(() => check());
chrome.runtime.onInstalled.addListener(() => check());
check();
