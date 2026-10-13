// The side chat (spec 22.3.1): where its window stands on the screen, and what address it shows.

'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const { placedAtTheSide, chatOf, widthOf } = require('./side-place.cjs');

test('the chat stands at the right edge of the screen, as tall as the room the system leaves', () => {
  const room = { x: 0, y: 25, width: 2560, height: 1340 };
  assert.deepEqual(placedAtTheSide(room, 400), { x: 2160, y: 25, width: 400, height: 1340 });
});

test('on a second screen it stands at that screen\'s own right edge', () => {
  const room = { x: -1920, y: 0, width: 1920, height: 1080 };
  assert.deepEqual(placedAtTheSide(room, 400), { x: -400, y: 0, width: 400, height: 1080 });
});

test('a screen narrower than the chat gives it the whole width and no more', () => {
  assert.deepEqual(placedAtTheSide({ x: 0, y: 0, width: 320, height: 600 }, 400), { x: 0, y: 0, width: 320, height: 600 });
});

test('the address is the chat alone of one page, with the token where no server is sent it', () => {
  const shown = chatOf('http://127.0.0.1:8765/?session=computer&beside#token=abc-123');
  assert.equal(shown, 'http://127.0.0.1:8765/?session=computer&beside#token=abc-123');
});

test('an address that is no page of a service is refused', () => {
  for (const given of ['', 'file:///etc/passwd', 'javascript:alert(1)', 'http://127.0.0.1:8765/?session=computer', 'not an address']) {
    assert.equal(chatOf(given), null, given);
  }
});

test('the width is the one the settings give, and there is none without them', () => {
  assert.equal(widthOf('400'), 400);
  assert.equal(widthOf(undefined), null);
  assert.equal(widthOf('wide'), null);
  assert.equal(widthOf('0'), null);
});
