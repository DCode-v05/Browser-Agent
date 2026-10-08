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

// Auto Mode and safeguards (spec 18).
export type SiteGrade = 'named' | 'added_read' | 'added_act';
export interface TaskSite {
  host: string;
  grade: SiteGrade;
}
export type Mode = 'every_action' | 'risky' | 'auto';
export type AutoState = 'off' | 'on' | 'paused' | 'waiting_for_task' | 'unavailable';
export type CheckStage = 'rule' | 'reviewer' | 'person' | 'limit';
export type CheckOutcome = 'run' | 'ask' | 'refuse';
export type LimitKind = 'calls' | 'minutes' | 'spend';
export type LimitScope = 'task' | 'session';

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
      /** Once this session has ended, a person can ask for a new one in its place. */
      restartable?: boolean;
      ts: number;
    }
  | { type: 'control_changed'; state: ControlState; since: number }
  | { type: 'step_started'; step: number; tool: string; label: string; target?: Box; ts: number }
  | { type: 'step_finished'; step: number; ok: boolean; ms: number; chars: number; summary: string; url: string }
  | { type: 'tab_changed'; tabs: TabInfo[] }
  /** `every_time`: the action pays, sends or deletes, so it cannot be allowed for the whole site. */
  | {
      type: 'approval_requested';
      id: string;
      tool: string;
      summary: string;
      site: string;
      expires_in_s: number;
      every_time?: boolean;
      /** Each reason in words, already written by the engine. */
      why?: string[];
      /** The exception of 18.6: text that was read on one site and is about to leave to another. */
      leaves?: { text: string; from_site: string; to_site: string };
      /** As the page shows it, e.g. "$84.00". */
      amount?: string;
      /** The check model's own sentence, for the person only. */
      said?: string;
      ts: number;
    }
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
  | { type: 'session_ended'; reason: EndReason; detail?: string; ts: number }
  // Auto Mode and safeguards (spec 18.10).
  | { type: 'task_set'; task: string; from: 'person' | 'agent'; sites: TaskSite[]; ts: number }
  /** The task line goes away; the sites stay known. */
  | { type: 'task_ended'; ts: number }
  | { type: 'sites_changed'; sites: TaskSite[] }
  | {
      type: 'check_decided';
      step: number;
      stage: CheckStage;
      outcome: CheckOutcome;
      findings: string[];
      /** The engine's own sentence. */
      reason: string;
      /** The check model's own sentence, for the person only. */
      said?: string;
      /** Present when the refused step can be allowed once. */
      refused_id?: string;
      ts: number;
    }
  /** A person pressed "Allow once" (from any viewer). */
  | { type: 'refused_allowed'; id: string; ts: number }
  | { type: 'page_flagged'; tab: string; site: string; rule: string; count: number; ts: number }
  | { type: 'auto_changed'; mode: Mode; state: AutoState; why?: string; ts: number }
  | {
      type: 'limit_reached';
      kind: LimitKind;
      limit: number;
      scope: LimitScope;
      /** What "Allow more" adds: steps for `calls`, minutes for `minutes`. Absent for `spend`. */
      more?: number;
      ts: number;
    }
  /** A person allowed more, or the task ended. */
  | { type: 'limit_lifted'; ts: number }
  | { type: 'questions_unanswered'; count: number; ts: number };

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
  | { type: 'task'; text: string }
  /** Ends the task the agent is on. The session goes on. */
  | { type: 'stop_task' }
  | { type: 'new_session' }
  // Auto Mode and safeguards (spec 18.10).
  | { type: 'resume_auto' }
  | { type: 'allow_refused'; id: string }
  | { type: 'extend_limit' }
  | { type: 'drop_site'; host: string }
  | { type: 'end_task' };

export type CommandType = ClientCommand['type'];
