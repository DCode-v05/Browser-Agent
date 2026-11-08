export interface ViewerOptions {
  staleAfterS: number;
  idleDividerS: number;
  releaseChord: string;
  toastMs: number;
  tickMs: number;
  pointerHoldMs: number;
  maxTaskChars: number;
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

export const PAGE = {
  heartbeatMs: 2000,
  roomsPollMs: 1500,
  suitePollMs: 1500,
  logLinesShown: 20,
  releaseAfterMs: 1000,
  besideWidth: 400,
  besideHeight: 760,
  screenRecordingPane: 'x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture',
  accessibilityPane: 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility',
} as const;

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
