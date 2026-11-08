'use strict';

function viewerOf(line) {
  const found = /^Viewer: (https?:\/\/[^/\s]+)\/#token=([\w-]+)\s*$/.exec(line);
  return found ? { origin: found[1], token: found[2] } : null;
}

function errorOf(line) {
  const found = /^error: (.+)$/.exec(line.trim());
  return found ? found[1] : null;
}

function chatAddress(viewer, page) {
  return `${viewer.origin}/?session=${encodeURIComponent(page)}&embed=1#token=${viewer.token}`;
}

function coreArguments(repository) {
  return ['run', '--project', repository, 'bap-browser', 'studio', '--desktop', '--dev'];
}

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

function placeable(rect) {
  const whole = (value) => (Number.isFinite(value) ? Math.max(0, Math.round(value)) : 0);
  return { x: whole(rect?.x), y: whole(rect?.y), width: whole(rect?.width), height: whole(rect?.height) };
}

function sessionsUp(answer, names) {
  const sessions = Array.isArray(answer?.sessions) ? answer.sessions : [];
  return names.every((name) => sessions.some((session) => session?.id === name));
}

module.exports = { viewerOf, errorOf, chatAddress, placeable, coreArguments, around, sessionsUp };
