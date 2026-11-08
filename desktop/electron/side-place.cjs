'use strict';

function placedAtTheSide(room, width) {
  const wide = Math.min(width, room.width);
  return { x: room.x + room.width - wide, y: room.y, width: wide, height: room.height };
}

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

function widthOf(given) {
  const width = Number(given);
  return Number.isInteger(width) && width > 0 ? width : null;
}

module.exports = { placedAtTheSide, chatOf, widthOf };
