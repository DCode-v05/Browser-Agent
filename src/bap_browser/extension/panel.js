// The side panel: it shows the session's viewer, which is the chat, and passes on to the pages of this
// window what the viewer says about who is driving, so that each page can show it (look.js).

const SESSION_FILE = 'session.json';
const LOOK = 'bap-browser.look';
// How often the session file is read again, and how often the pages are told again. A page that has
// just loaded learns within that time who is driving.
const RELOAD_MS = 2000;
const RETELL_MS = 1000;

const frame = document.getElementById('viewer');
const waiting = document.getElementById('waiting');

/** The viewer's address now shown, and its origin: only messages from there are passed on. */
let shown = '';
let origin = '';
/** What the viewer said last about who is driving. */
let look = null;

async function connect() {
  let viewer = '';
  try {
    // The core writes this file when a session starts and removes it when the session ends.
    const answer = await fetch(chrome.runtime.getURL(SESSION_FILE), { cache: 'no-store' });
    viewer = answer.ok ? ((await answer.json()).viewer ?? '') : '';
  } catch {
    viewer = '';
  }
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
  frame.hidden = !viewer;
  waiting.hidden = Boolean(viewer);
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

setInterval(connect, RELOAD_MS);
setInterval(() => look && tell(look), RETELL_MS);
connect();
