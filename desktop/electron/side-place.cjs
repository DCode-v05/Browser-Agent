// The side chat (spec 22.3.1): where its window stands on the screen, and what address it may show.

'use strict';

/** The window's place: at the right edge of the room the system leaves on a screen, and as tall. */
function placedAtTheSide(room, width) {
  const wide = Math.min(width, room.width);
  return { x: room.x + room.width - wide, y: room.y, width: wide, height: room.height };
}

/**
 * The address to show, or null when it is not the chat alone of a page of a service. The window
 * floats above every app and is signed in: it shows that one thing and nothing else.
 */
function chatOf(given) {
  let address;
  try {
    address = new URL(given);
  } catch {
    return null;
  }
  const aPage = address.protocol === 'http:' || address.protocol === 'https:';
  const theChatAlone = address.searchParams.has('beside') && address.searchParams.has('session');
  return aPage && theChatAlone ? address.href : null;
}

/** The width the settings give (`server.side_chat_width`), or null: this file holds no width of its own. */
function widthOf(given) {
  const width = Number(given);
  return Number.isInteger(width) && width > 0 ? width : null;
}

module.exports = { placedAtTheSide, chatOf, widthOf };
