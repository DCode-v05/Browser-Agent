// Values the service owns (`viewer.*` in its configuration) and hands to the viewer. Until the
// service does, these mirror its defaults.

export interface ViewerOptions {
  /** When "Live" becomes the stale notice, in seconds. */
  staleAfterS: number;
  /** The gap between steps that becomes an idle divider, in seconds. */
  idleDividerS: number;
  /** The keys that leave the live picture during takeover. */
  releaseChord: string;
  /** How long a toast stays, in milliseconds. */
  toastMs: number;
  /** How often the clock on screen is refreshed, in milliseconds. 0 leaves it still. */
  tickMs: number;
  /** How long the outline and the click mark stay after the agent has acted, in milliseconds. */
  pointerHoldMs: number;
  /** The longest task the chat takes, in characters. */
  maxTaskChars: number;
  /** How long a pressed control shows as working when nothing came of the press, in milliseconds. */
  workingMs: number;
}

export const DEFAULT_OPTIONS: ViewerOptions = {
  staleAfterS: 5,
  idleDividerS: 10,
  releaseChord: 'Ctrl+Alt+Enter',
  toastMs: 4000,
  tickMs: 1000,
  pointerHoldMs: 600,
  maxTaskChars: 4000,
  workingMs: 8000,
};

/** Values that are the page's own: the service has no say in them. */
export const PAGE = {
  /** How often a recorded session says its picture is current, in milliseconds. */
  heartbeatMs: 2000,
  /** How often the window asks the service where its pages stand, in milliseconds. */
  roomsPollMs: 1500,
  /** How often a run of a task set that is under way is asked about, in milliseconds. */
  suitePollMs: 1500,
  /** How many lines of a browser's log its card shows. */
  logLinesShown: 20,
  /** How long after the pointer has left the live picture a held key is let go, in milliseconds. */
  releaseAfterMs: 1000,
  /** The panes of the Mac's System Settings where a person allows the helper. */
  screenRecordingPane: 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture',
  accessibilityPane: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility',
} as const;

/** True when a key event is the release chord, such as "Ctrl+Alt+Enter". */
export function matchesChord(event: { key: string; ctrlKey: boolean; altKey: boolean; shiftKey: boolean; metaKey: boolean }, chord: string): boolean {
  const parts = chord.split('+').map((part) => part.trim().toLowerCase());
  const key = parts.at(-1);
  const wants = (name: string) => parts.slice(0, -1).includes(name);
  return (
    event.key.toLowerCase() === key &&
    event.ctrlKey === wants('ctrl') &&
    event.altKey === wants('alt') &&
    event.shiftKey === wants('shift') &&
    event.metaKey === wants('meta')
  );
}
