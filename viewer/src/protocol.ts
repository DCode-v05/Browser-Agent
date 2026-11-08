export type ControlState = 'agent' | 'waiting_approval' | 'person_requested' | 'person' | 'paused' | 'ended';
export type Backend = 'remote_headless' | 'takeover_chrome' | 'bundled_chromium' | 'contained_desktop';
export type Surface = 'web' | 'mobile' | 'desktop';

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
  attention?: boolean;
}

export type ApprovalOutcome = 'allowed' | 'allowed_site' | 'denied' | 'expired' | 'unwatched';
export type HelpKind = 'login' | 'verification' | 'payment' | 'other';
export type HelpOutcome = 'done' | 'could_not' | 'timed_out';
export type DialogKind = 'alert' | 'confirm' | 'prompt' | 'beforeunload';
export type DialogOutcome = 'accepted' | 'dismissed' | 'timed_out';
export type EndReason = 'person' | 'agent' | 'timeout' | 'failed';

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
      chat?: boolean;
      on_screen?: boolean;
      restartable?: boolean;
      ts: number;
    }
  | { type: 'control_changed'; state: ControlState; since: number }
  | { type: 'step_started'; step: number; tool: string; label: string; target?: Box; ts: number }
  | { type: 'step_finished'; step: number; ok: boolean; ms: number; chars: number; summary: string; url: string }
  | { type: 'tab_changed'; tabs: TabInfo[] }
  | {
      type: 'approval_requested';
      id: string;
      tool: string;
      summary: string;
      site: string;
      expires_in_s: number;
      every_time?: boolean;
      why?: string[];
      leaves?: { text: string; from_site: string; to_site: string };
      amount?: string;
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
  | { type: 'message'; id: number; role: 'person' | 'agent'; text: string; failed?: boolean; ts: number }
  | { type: 'task_changed'; working: boolean; ts: number }
  | { type: 'picture_current'; ts: number }
  | { type: 'session_ended'; reason: EndReason; detail?: string; ts: number }
  | { type: 'task_set'; task: string; from: 'person' | 'agent'; sites: TaskSite[]; ts: number }
  | { type: 'task_ended'; ts: number }
  | { type: 'sites_changed'; sites: TaskSite[] }
  | {
      type: 'check_decided';
      step: number;
      stage: CheckStage;
      outcome: CheckOutcome;
      findings: string[];
      reason: string;
      said?: string;
      refused_id?: string;
      ts: number;
    }
  | { type: 'refused_allowed'; id: string; ts: number }
  | { type: 'page_flagged'; tab: string; site: string; rule: string; count: number; ts: number }
  | { type: 'auto_changed'; mode: Mode; state: AutoState; why?: string; ts: number }
  | {
      type: 'limit_reached';
      kind: LimitKind;
      limit: number;
      scope: LimitScope;
      more?: number;
      ts: number;
    }
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
  | { type: 'seen'; visible: boolean }
  | { type: 'stop_task' }
  | { type: 'new_session' }
  | { type: 'resume_auto' }
  | { type: 'allow_refused'; id: string }
  | { type: 'extend_limit' }
  | { type: 'drop_site'; host: string }
  | { type: 'end_task' };

export type CommandType = ClientCommand['type'];
