// What the agent's core says on its error stream, read by the desktop app: where the session's
// viewer is, and what went wrong when the core could not start.

'use strict';

/** The service's address and the session's token, from the line that names the viewer. */
function viewerOf(line) {
  const found = /^Viewer: (https?:\/\/[^/\s]+)\/#token=([\w-]+)\s*$/.exec(line);
  return found ? { origin: found[1], token: found[2] } : null;
}

/** What the core says when it stops with an error, without the word that marks it. */
function errorOf(line) {
  const found = /^error: (.+)$/.exec(line.trim());
  return found ? found[1] : null;
}

/**
 * Where the chat is shown from: the viewer as a guest of the app, which drops its own product name.
 * The token stays in the fragment, which no server is sent.
 */
function chatAddress(viewer) {
  return `${viewer.origin}/?embed=1#token=${viewer.token}`;
}

/** A rectangle the app's window can place a view at: whole pixels, never negative. */
function placeable(rect) {
  const whole = (value) => (Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0);
  return { x: whole(rect?.x), y: whole(rect?.y), width: whole(rect?.width), height: whole(rect?.height) };
}

module.exports = { viewerOf, errorOf, chatAddress, placeable };
