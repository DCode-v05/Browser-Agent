'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');

const { viewerOf, errorOf, chatAddress, placeable } = require('./core-line.cjs');

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

test('the chat is the viewer as a guest, with the token where no server sees it', () => {
  assert.equal(chatAddress({ origin: 'http://127.0.0.1:53412', token: 'abc' }), 'http://127.0.0.1:53412/?embed=1#token=abc');
});

test('a view is placed at whole pixels, and never at a negative or missing size', () => {
  assert.deepEqual(placeable({ x: 10.4, y: 56.6, width: 900.5, height: 700 }), { x: 10, y: 57, width: 901, height: 700 });
  assert.deepEqual(placeable({ x: -5, y: 0, width: -1, height: Number.NaN }), { x: 0, y: 0, width: 0, height: 0 });
  assert.deepEqual(placeable(undefined), { x: 0, y: 0, width: 0, height: 0 });
});
