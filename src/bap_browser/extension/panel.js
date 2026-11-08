const LOOK = 'bap-browser.look';
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

let shown = '';
let origin = '';
let look = null;
let asked = null;

function show(state) {
  showViewer(state.viewer);
  frame.hidden = !shown;
  stopped.hidden = !state.stopped;
  connecting.hidden = state.stopped || Boolean(shown) || !state.wanted;
  waiting.hidden = state.stopped || Boolean(shown) || state.wanted;

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
