// The viewer protocol (spec 4.8): events from the service, commands to it.

export type ControlState = 'agent' | 'waiting_approval' | 'person_requested' | 'person' | 'paused' | 'ended';
export type Backend = 'remote_headless' | 'takeover_chrome' | 'bundled_chromium';
export type Surface = 'web' | 'mobile' | 'desktop';

/** A rectangle in page pixels. */
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface TabInfo {
  id: string;
  title: string;
  url: string;
  active: boolean;
  /** The tab wants a person's attention, for example a dialog opened in it. */
  attention?: boolean;
}

export type ApprovalOutcome = 'allowed' | 'allowed_site' | 'denied' | 'expired' | 'unwatched';
export type HelpKind = 'login' | 'verification' | 'payment' | 'other';
export type HelpOutcome = 'done' | 'could_not' | 'timed_out';
export type DialogKind = 'alert' | 'confirm' | 'prompt' | 'beforeunload';
export type DialogOutcome = 'accepted' | 'dismissed' | 'timed_out';
export type EndReason = 'person' | 'agent' | 'timeout' | 'failed';

export type ServerEvent =
  | {
      type: 'session_started';
      session: string;
      agent: string;
      backend: Backend;
      browser: string;
      viewport: { width: number; height: number };
      /** The agent takes its tasks from the chat in the viewer. */
      chat?: boolean;
      /** The browser is a window on the person's own screen. */
      on_screen?: boolean;
      ts: number;
    }
  | { type: 'control_changed'; state: ControlState; since: number }
  | { type: 'step_started'; step: number; tool: string; label: string; target?: Box; ts: number }
  | { type: 'step_finished'; step: number; ok: boolean; ms: number; chars: number; summary: string; url: string }
  | { type: 'tab_changed'; tabs: TabInfo[] }
  | { type: 'approval_requested'; id: string; tool: string; summary: string; site: string; expires_in_s: number; ts: number }
  | { type: 'approval_closed'; id: string; outcome: ApprovalOutcome }
  | { type: 'help_requested'; id: string; reason: string; kind: HelpKind; expires_in_s: number; ts: number }
  | { type: 'help_closed'; id: string; outcome: HelpOutcome }
  | { type: 'dialog_opened'; id: string; kind: DialogKind; text: string; expires_in_s: number; ts: number }
  | { type: 'dialog_closed'; id: string; outcome: DialogOutcome }
  | { type: 'download_saved'; name: string; size: number; ts: number }
  | { type: 'navigation_blocked'; url: string; reason: string; ts: number }
  | { type: 'settings_changed'; changes: Record<string, unknown> }
  /** One message of the chat: a task a person gave, or what the agent answered. */
  | { type: 'message'; id: number; role: 'person' | 'agent'; text: string; failed?: boolean; ts: number }
  /** The agent began a task, or finished it and waits for the next. */
  | { type: 'task_changed'; working: boolean; ts: number }
  /** The page has not changed, so the last picture is still what the browser shows. */
  | { type: 'picture_current'; ts: number }
  | { type: 'session_ended'; reason: EndReason; detail?: string; ts: number };

export type ClientCommand =
  | { type: 'auth'; token: string }
  | { type: 'approve'; id: string; scope: 'once' | 'site' }
  | { type: 'deny'; id: string }
  | { type: 'pause' }
  | { type: 'resume' }
  | { type: 'stop' }
  | { type: 'take_over' }
  | { type: 'hand_back' }
  | { type: 'done' }
  | { type: 'could_not' }
  | { type: 'pointer'; action: 'move' | 'down' | 'up'; x: number; y: number; button: number }
  | { type: 'key'; action: 'down' | 'up'; key: string; code: string }
  | { type: 'wheel'; x: number; y: number; dx: number; dy: number }
  | { type: 'select_tab'; id: string }
  | { type: 'task'; text: string };

export type CommandType = ClientCommand['type'];
