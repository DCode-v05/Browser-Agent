'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { viewerOf, errorOf, chatAddress, placeable, coreArguments, around, sessionsUp } = require('./core-line.cjs');

test('the line that names the viewer gives the service and the token', () => {
  assert.deepEqual(viewerOf('Viewer: http://127.0.0.1:53412/#token=abc-DEF_123'), { origin: 'http://127.0.0.1:53412', token: 'abc-DEF_123' });
  assert.deepEqual(viewerOf('Viewer: http://127.0.0.1:53412/#token=abc\r'), { origin: 'http://127.0.0.1:53412', token: 'abc' });
});

test('no other line is taken for it', () => {
  for (const line of ['Demo site: http://127.0.0.1:53412/demo-site/checkin.html', 'INFO:uvicorn.error:Started server process [1]', 'Viewer: ', 'Viewer: http://127.0.0.1:1/', '']) {
    assert.equal(viewerOf(line), null, line);
  }
});

test('an error line gives what went wrong', () => {
  assert.equal(errorOf('error: OPENAI_API_KEY is not set. Put a line OPENAI_API_KEY=... in a file named .env'), 'OPENAI_API_KEY is not set. Put a line OPENAI_API_KEY=... in a file named .env');
  assert.equal(errorOf('Type a task in the viewer\'s chat. Press Ctrl+C to end.'), null);
});

test('each page is one page of the studio, as a guest, with the token where no server sees it', () => {
  const viewer = { origin: 'http://127.0.0.1:53412', token: 'abc' };
  assert.equal(chatAddress(viewer, 'builtin'), 'http://127.0.0.1:53412/?session=builtin&embed=1#token=abc');
  assert.equal(chatAddress(viewer, 'computer'), 'http://127.0.0.1:53412/?session=computer&embed=1#token=abc');
});

test('the core is the studio with the desktop app\'s two pages: its own browser, and the computer', () => {
  // `--dev`: the token is this run's own, made by the app and shown to nobody, so it stays the admin's.
  assert.deepEqual(coreArguments('/repo'), ['run', '--project', '/repo', 'bap-browser', 'studio', '--desktop', '--dev']);
});

test('the computer takes the room of the browser and the chat together', () => {
  const browser = { x: 60, y: 56, width: 900, height: 700 };
  const chat = { x: 972, y: 56, width: 400, height: 700 };
  assert.deepEqual(around(browser, chat), { x: 60, y: 56, width: 1312, height: 700 });
});

test('a view is placed at whole pixels, and never at a negative or missing size', () => {
  assert.deepEqual(placeable({ x: 10.4, y: 56.6, width: 900.5, height: 700 }), { x: 10, y: 57, width: 901, height: 700 });
  assert.deepEqual(placeable({ x: -5, y: 0, width: -1, height: Number.NaN }), { x: 0, y: 0, width: 0, height: 0 });
  assert.deepEqual(placeable(undefined), { x: 0, y: 0, width: 0, height: 0 });
});

test('a page is shown once the studio has a session on it, and not before', () => {
  const both = ['builtin', 'computer'];
  assert.equal(sessionsUp({ sessions: [{ id: 'computer', state: 'agent' }] }, both), false);
  assert.equal(sessionsUp({ sessions: [{ id: 'builtin', state: 'agent' }, { id: 'computer', state: 'agent' }] }, both), true);
  assert.equal(sessionsUp(null, both), false);
  assert.equal(sessionsUp({ error: 'no' }, both), false);
});
