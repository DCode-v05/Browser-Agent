// The side panel. It does three things:
//  1. shows the session's viewer, which is the chat;
//  2. passes on to the pages of this window what the viewer says about who is driving, so that each
//     page can show it (look.js);
//  3. is where the person answers the bridge's questions and stops the agent: whether it may work on
//     a site, and the extension's own Stop (spec 8.8).
// The bridge itself is in the background (background.js), so this panel can be closed while the
// agent works.

const LOOK = 'bap-browser.look';
// How often the background is asked where things stand, and how often the pages are told again. A
// page that has just loaded learns within that time who is driving.
const RELOAD_MS = 2000;
const RETELL_MS = 1000;

const frame = document.getElementById('viewer');
const waiting = document.getElementById('waiting');
const connecting = document.getElementById('connecting');
const stopped = document.getElementById('stopped');
const bar = document.getElementById('bridge');
const barText = document.getElementById('bridge-text');
const stop = document.getElementById('stop');
const card = document.getElementById('question');
const cardSite = document.getElementById('question-site');
const cardDoing = document.getElementById('question-doing');
const always = document.getElementById('always');

/** The viewer's address now shown, and its origin: only messages from there are passed on. */
let shown = '';
let origin = '';
/** What the viewer said last about who is driving. */
let look = null;
/** The question on screen now. */
let asked = null;

function show(state) {
  showViewer(state.viewer);
  frame.hidden = !shown;
  stopped.hidden = !state.stopped;
  connecting.hidden = state.stopped || Boolean(shown) || !state.wanted;
  waiting.hidden = state.stopped || Boolean(shown) || state.wanted;

  // The bridge's own line: only where there is a bridge, which is take-over Chrome.
  bar.hidden = !state.wanted || state.stopped;
  bar.dataset.state = state.connected ? 'connected' : 'reconnecting';
  barText.textContent = state.connected
    ? state.attached
      ? 'The agent is connected to its tab in this browser.'
      : 'The agent is connected.'
    : 'Reconnecting to the agent…';
  stop.hidden = !state.connected;

  asked = state.question;
  card.hidden = !asked;
  if (asked) {
    cardSite.textContent = asked.site;
    cardDoing.textContent = asked.summary;
    always.hidden = !asked.always;
  }
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

async function refresh() {
  try {
    show(await chrome.runtime.sendMessage({ type: 'bap.check' }));
  } catch {
    // The background is starting again. It is asked again in a moment.
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (typeof message === 'object' && message !== null && message.type === 'bap.state') show(message.state);
});

for (const button of card.querySelectorAll('button[data-choice]')) {
  button.addEventListener('click', () => {
    if (!asked) return;
    chrome.runtime.sendMessage({ type: 'bap.answer', id: asked.id, choice: button.dataset.choice });
    card.hidden = true;
  });
}

stop.addEventListener('click', () => chrome.runtime.sendMessage({ type: 'bap.stop' }));

setInterval(refresh, RELOAD_MS);
setInterval(() => look && tell(look), RETELL_MS);
refresh();
