// What the desktop app gives its shell (electron/preload.cjs).

export interface DesktopState {
  /** starting: the agent's core is coming up. running: the chat is live. stopped: the core is gone. */
  core: 'starting' | 'running' | 'stopped';
  /** Why the core stopped, in its own words. */
  message: string;
  /** The address the agent's browser is at. */
  address: string;
  canGoBack: boolean;
  canGoForward: boolean;
}

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type DemoPage = 'start' | 'checkin' | 'signup';

declare global {
  interface Window {
    desktop: {
      onState(listener: (state: DesktopState) => void): () => void;
      place(rects: { agent: Rect; chat: Rect }): void;
      go(action: 'back' | 'forward' | 'reload'): void;
      go(action: 'open', page: DemoPage): void;
      startAgain(): void;
    };
  }
}
