import type {
  ApprovalOutcome,
  AutoState,
  Backend,
  Box,
  ControlState,
  DialogKind,
  EndReason,
  HelpKind,
  HelpOutcome,
  LimitKind,
  LimitScope,
  Mode,
  ServerEvent,
  TabInfo,
  TaskSite,
} from '../protocol';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'refused';

export type StepMark = { kind: 'checked' } | { kind: 'allowed' } | { kind: 'refused'; reason: string };

export interface Step {
  n: number;
  tool: string;
  label: string;
  target?: Box;
  startedAt: number;
  status: 'running' | 'ok' | 'failed';
  ms?: number;
  chars?: number;
  summary?: string;
  url?: string;
  picture?: string;
  mark?: StepMark;
}

export interface Approval {
  id: string;
  tool: string;
  summary: string;
  site: string;
  everyTime: boolean;
  requestedAt: number;
  expiresAt: number;
  why?: string[];
  leaves?: { text: string; fromSite: string; toSite: string };
  amount?: string;
  said?: string;
}

export interface HelpRequest {
  id: string;
  reason: string;
  kind: HelpKind;
  requestedAt: number;
  expiresAt: number;
}

export interface PageDialog {
  id: string;
  kind: DialogKind;
  text: string;
  expiresAt: number;
}

export type Notice = { id: number } & (
  | { kind: 'approval'; outcome: ApprovalOutcome; summary: string }
  | { kind: 'help'; outcome: HelpOutcome; reason: string }
  | { kind: 'download'; name: string; size: number }
);

type NewNotice = Notice extends infer N ? (N extends { id: number } ? Omit<N, 'id'> : never) : never;

export interface ChatMessage {
  id: number;
  role: 'person' | 'agent';
  text: string;
  failed: boolean;
  at: number;
}

export interface Chat {
  enabled: boolean;
  working: boolean;
  messages: ChatMessage[];
}

export interface SessionInfo {
  id: string;
  agent: string;
  backend: Backend;
  browser: string;
  viewport: { width: number; height: number };
  onScreen: boolean;
  restartable: boolean;
  startedAt: number;
}

export interface TaskInfo {
  task: string;
  from: 'person' | 'agent';
  sites: TaskSite[];
}

export interface AutoInfo {
  mode: Mode;
  state: AutoState;
  why?: string;
}

export interface RefusedStep {
  step: number;
  id: string | null;
  label: string;
  reason: string;
  allowed: boolean;
}

export interface FlaggedPage {
  id: number;
  tab: string;
  site: string;
}

export interface LimitInfo {
  kind: LimitKind;
  limit: number;
  scope: LimitScope;
  more?: number;
}

export interface UnansweredMarker {
  key: string;
  count: number;
  at: number;
}

export interface ViewerState {
  connection: ConnectionStatus;
  session: SessionInfo | null;
  control: ControlState | 'none';
  controlSince: number;
  blocked: { url: string; reason: string; at: number } | null;
  tabs: TabInfo[];
  url: string;
  steps: Step[];
  chat: Chat;
  chars: number;
  approval: Approval | null;
  help: HelpRequest | null;
  dialog: PageDialog | null;
  downloads: { name: string; size: number }[];
  notices: Notice[];
  caughtUp: boolean;
  noticesSeen: number;
  ended: { reason: EndReason; detail?: string; at: number } | null;
  frame: { src: string; at: number } | null;
  settingsVersion: number;
  auto: AutoInfo | null;
  task: TaskInfo | null;
  refused: RefusedStep[];
  flagged: FlaggedPage[];
  limit: LimitInfo | null;
  unanswered: UnansweredMarker[];
}

export const initialState: ViewerState = {
  connection: 'connecting',
  session: null,
  control: 'none',
  controlSince: 0,
  blocked: null,
  tabs: [],
  url: '',
  steps: [],
  chat: { enabled: false, working: false, messages: [] },
  chars: 0,
  approval: null,
  help: null,
  dialog: null,
  downloads: [],
  notices: [],
  caughtUp: false,
  noticesSeen: 0,
  ended: null,
  frame: null,
  settingsVersion: 0,
  auto: null,
  task: null,
  refused: [],
  flagged: [],
  limit: null,
  unanswered: [],
};

export type Action =
  | { type: 'event'; event: ServerEvent; picture?: string }
  | { type: 'frame'; src: string; at: number }
  | { type: 'connection'; status: ConnectionStatus }
  | { type: 'caught_up' };

export function reduce(state: ViewerState, action: Action): ViewerState {
  switch (action.type) {
    case 'frame':
      return { ...state, frame: { src: action.src, at: action.at } };
    case 'connection':
      return { ...state, connection: action.status, caughtUp: action.status === 'connected' ? false : state.caughtUp };
    case 'caught_up':
      return { ...state, caughtUp: true, noticesSeen: state.notices.at(-1)?.id ?? 0 };
    case 'event':
      return applyEvent(state, action.event, action.picture);
  }
}

export function unseenNotices(state: ViewerState): Notice[] {
  return state.caughtUp ? state.notices.filter((notice) => notice.id > state.noticesSeen) : [];
}

function withNotice(state: ViewerState, notice: NewNotice): ViewerState {
  const id = (state.notices.at(-1)?.id ?? 0) + 1;
  return { ...state, notices: [...state.notices, { ...notice, id } as Notice] };
}

function applyEvent(state: ViewerState, event: ServerEvent, picture: string | undefined): ViewerState {
  switch (event.type) {
    case 'session_started':
      return {
        ...initialState,
        connection: state.connection,
        caughtUp: state.caughtUp,
        frame: state.frame,
        settingsVersion: state.settingsVersion,
        session: {
          id: event.session,
          agent: event.agent,
          backend: event.backend,
          browser: event.browser,
          viewport: event.viewport,
          onScreen: event.on_screen === true,
          restartable: event.restartable === true,
          startedAt: event.ts,
        },
        control: 'agent',
        controlSince: event.ts,
        chat: { ...initialState.chat, enabled: event.chat === true },
      };

    case 'control_changed':
      return { ...state, control: event.state, controlSince: event.since };

    case 'step_started': {
      const step: Step = { n: event.step, tool: event.tool, label: event.label, startedAt: event.ts, status: 'running' };
      if (event.target) step.target = event.target;
      return { ...state, blocked: null, steps: [...state.steps, step] };
    }

    case 'step_finished': {
      if (!state.steps.some((step) => step.n === event.step)) return state;
      const steps = state.steps.map((step) =>
        step.n === event.step
          ? {
              ...step,
              status: event.ok ? ('ok' as const) : ('failed' as const),
              ms: event.ms,
              chars: event.chars,
              summary: event.summary,
              url: event.url,
              picture,
            }
          : step,
      );
      return { ...state, steps, chars: state.chars + event.chars, url: event.url || state.url };
    }

    case 'tab_changed': {
      const active = event.tabs.find((tab) => tab.active);
      return { ...state, tabs: event.tabs, url: active ? active.url : state.url };
    }

    case 'approval_requested':
      return {
        ...state,
        approval: {
          id: event.id,
          tool: event.tool,
          summary: event.summary,
          site: event.site,
          everyTime: event.every_time === true,
          requestedAt: event.ts,
          expiresAt: event.ts + event.expires_in_s,
          why: event.why,
          leaves: event.leaves && { text: event.leaves.text, fromSite: event.leaves.from_site, toSite: event.leaves.to_site },
          amount: event.amount,
          said: event.said,
        },
      };

    case 'approval_closed': {
      if (state.approval?.id !== event.id) return state;
      const steps =
        event.outcome === 'allowed' || event.outcome === 'allowed_site'
          ? state.steps.map((step) => (step.status === 'running' ? { ...step, mark: { kind: 'allowed' as const } } : step))
          : state.steps;
      return withNotice({ ...state, approval: null, steps }, { kind: 'approval', outcome: event.outcome, summary: state.approval.summary });
    }

    case 'help_requested':
      return {
        ...state,
        help: { id: event.id, reason: event.reason, kind: event.kind, requestedAt: event.ts, expiresAt: event.ts + event.expires_in_s },
      };

    case 'help_closed': {
      if (state.help?.id !== event.id) return state;
      return withNotice({ ...state, help: null }, { kind: 'help', outcome: event.outcome, reason: state.help.reason });
    }

    case 'dialog_opened':
      return { ...state, dialog: { id: event.id, kind: event.kind, text: event.text, expiresAt: event.ts + event.expires_in_s } };

    case 'dialog_closed':
      return state.dialog?.id === event.id ? { ...state, dialog: null } : state;

    case 'download_saved':
      return withNotice(
        { ...state, downloads: [...state.downloads, { name: event.name, size: event.size }] },
        { kind: 'download', name: event.name, size: event.size },
      );

    case 'navigation_blocked':
      return { ...state, blocked: { url: event.url, reason: event.reason, at: event.ts } };

    case 'settings_changed':
      return { ...state, settingsVersion: state.settingsVersion + 1 };

    case 'message': {
      if (state.chat.messages.some((message) => message.id === event.id)) return state;
      const message: ChatMessage = { id: event.id, role: event.role, text: event.text, failed: event.failed === true, at: event.ts };
      return { ...state, chat: { ...state.chat, messages: [...state.chat.messages, message] } };
    }

    case 'task_changed':
      return { ...state, chat: { ...state.chat, working: event.working } };

    case 'picture_current':
      return state.frame ? { ...state, frame: { src: state.frame.src, at: event.ts } } : state;

    case 'session_ended':
      return {
        ...state,
        control: 'ended',
        controlSince: event.ts,
        approval: null,
        help: null,
        dialog: null,
        chat: { ...state.chat, working: false },
        ended: { reason: event.reason, detail: event.detail, at: event.ts },
        limit: null,
      };

    case 'task_set':
      return { ...state, task: { task: event.task, from: event.from, sites: event.sites } };

    case 'task_ended':
      return { ...state, task: null };

    case 'sites_changed':
      return state.task ? { ...state, task: { ...state.task, sites: event.sites } } : state;

    case 'check_decided': {
      const mark: StepMark | null = event.stage === 'reviewer' && event.outcome === 'run' ? { kind: 'checked' } : event.outcome === 'refuse' ? { kind: 'refused', reason: event.reason } : null;
      const steps = mark ? state.steps.map((step) => (step.n === event.step ? { ...step, mark } : step)) : state.steps;
      if (event.outcome !== 'refuse') return { ...state, steps };
      const label = state.steps.find((step) => step.n === event.step)?.label ?? '';
      const refused: RefusedStep = { step: event.step, id: event.refused_id ?? null, label, reason: event.reason, allowed: false };
      return { ...state, steps, refused: [...state.refused, refused] };
    }

    case 'refused_allowed':
      return { ...state, refused: state.refused.map((item) => (item.id === event.id ? { ...item, allowed: true } : item)) };

    case 'page_flagged': {
      const id = (state.flagged.at(-1)?.id ?? 0) + 1;
      return { ...state, flagged: [...state.flagged, { id, tab: event.tab, site: event.site }] };
    }

    case 'auto_changed':
      return { ...state, auto: { mode: event.mode, state: event.state, why: event.why } };

    case 'limit_reached':
      return { ...state, limit: { kind: event.kind, limit: event.limit, scope: event.scope, more: event.more } };

    case 'limit_lifted':
      return { ...state, limit: null };

    case 'questions_unanswered':
      return { ...state, unanswered: [...state.unanswered, { key: `unanswered-${state.unanswered.length + 1}`, count: event.count, at: event.ts }] };

    default:
      return state;
  }
}
