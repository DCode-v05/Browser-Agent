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
 * Where one page of the studio is shown from: its browser's chat, or the computer. It is the viewer as
 * a guest of the app, which drops its own product name. The token stays in the fragment, which no
 * server is sent.
 */
function chatAddress(viewer, page) {
  return `${viewer.origin}/?session=${encodeURIComponent(page)}&embed=1#token=${viewer.token}`;
}

/**
 * How the core is started: the studio with the desktop app's two pages (spec 14.3), its own browser,
 * which the core drives by attaching to it, and the computer. `--dev`: the core's token is this run's
 * own, made by the app and shown to nobody, so it stays the admin's after a password is set.
 */
function coreArguments(repository) {
  return ['run', '--project', repository, 'bap-browser', 'studio', '--desktop', '--dev'];
}

/** The room two views take together, side by side: the computer is shown there. */
function around(one, other) {
  const x = Math.min(one.x, other.x);
  const y = Math.min(one.y, other.y);
  return {
    x,
    y,
    width: Math.max(one.x + one.width, other.x + other.width) - x,
    height: Math.max(one.y + one.height, other.y + other.height) - y,
  };
}

/** A rectangle the app's window can place a view at: whole pixels, never negative. */
function placeable(rect) {
  const whole = (value) => (Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0);
  return { x: whole(rect?.x), y: whole(rect?.y), width: whole(rect?.width), height: whole(rect?.height) };
}

/** Whether the studio has a session on each of these pages, from its answer to `/api/sessions`. */
function sessionsUp(answer, names) {
  const sessions = Array.isArray(answer?.sessions) ? answer.sessions : [];
  return names.every((name) => sessions.some((session) => session?.id === name));
}

module.exports = { viewerOf, errorOf, chatAddress, placeable, coreArguments, around, sessionsUp };
