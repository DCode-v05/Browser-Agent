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
