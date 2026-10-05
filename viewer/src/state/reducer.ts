// The session as the viewer knows it: one reducer fed by the event stream (spec 9.11), so any
// state can be reproduced from a recorded stream.

import type {
  ApprovalOutcome,
  Backend,
  Box,
  ControlState,
  DialogKind,
  EndReason,
  HelpKind,
  HelpOutcome,
  ServerEvent,
  TabInfo,
} from '../protocol';

/** `refused`: the service did not accept the token. Trying again would change nothing. */
export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'refused';

export interface Step {
  n: number;
  tool: string;
  /** What the agent is doing, shown while the step runs. */
  label: string;
  target?: Box;
  startedAt: number;
  status: 'running' | 'ok' | 'failed';
  ms?: number;
  chars?: number;
  /** One sentence saying what happened, shown once the step has finished. */
  summary?: string;
  url?: string;
  /** The picture on screen when the step finished. */
  picture?: string;
}

export interface Approval {
  id: string;
  tool: string;
  summary: string;
  site: string;
  requestedAt: number;
  expiresAt: number;
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

/** The conversation in which a person gives the agent its tasks. */
export interface Chat {
  /** False when this session's agent takes no tasks from the viewer: there is then no chat to show. */
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
  /** The browser is a window on the person's own screen, so there is no picture of it to show. */
  onScreen: boolean;
  startedAt: number;
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
  /** Characters returned to the agent so far: what the session has cost in tokens, roughly. */
  chars: number;
  approval: Approval | null;
  help: HelpRequest | null;
  dialog: PageDialog | null;
  downloads: { name: string; size: number }[];
  /** Things that happened and deserve a word to the person. Each is shown once, by its id. */
  notices: Notice[];
  /** False while a connection replays what had already happened. Nothing replayed is shown as new. */
  caughtUp: boolean;
  /** The id of the last notice that was replayed. Those are not shown again. */
  noticesSeen: number;
  ended: { reason: EndReason; detail?: string; at: number } | null;
  frame: { src: string; at: number } | null;
  /** Goes up when the settings changed, so the settings screen reads them again. */
  settingsVersion: number;
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
};

export type Action =
  | { type: 'event'; event: ServerEvent; picture?: string }
  | { type: 'frame'; src: string; at: number }
  | { type: 'connection'; status: ConnectionStatus }
  /** Everything that had already happened has been replayed. */
  | { type: 'caught_up' };

export function reduce(state: ViewerState, action: Action): ViewerState {
  switch (action.type) {
    case 'frame':
      return { ...state, frame: { src: action.src, at: action.at } };
    case 'connection':
      // A connection that has just opened replays the session before anything new arrives.
      return { ...state, connection: action.status, caughtUp: action.status === 'connected' ? false : state.caughtUp };
    case 'caught_up':
      return { ...state, caughtUp: true, noticesSeen: state.notices.at(-1)?.id ?? 0 };
    case 'event':
      return applyEvent(state, action.event, action.picture);
  }
}

/** The notices a person has not been shown yet. */
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
      // A new step means the agent has moved on from a blocked page.
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
          requestedAt: event.ts,
          expiresAt: event.ts + event.expires_in_s,
        },
      };

    case 'approval_closed': {
      if (state.approval?.id !== event.id) return state;
      return withNotice({ ...state, approval: null }, { kind: 'approval', outcome: event.outcome, summary: state.approval.summary });
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
      // A connection that comes back replays the chat. A message already here is not added twice.
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
      };

    default:
      // An event from a newer service than this viewer knows. It changes nothing here.
      return state;
  }
}
