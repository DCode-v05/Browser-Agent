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

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting';

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

export interface SessionInfo {
  id: string;
  agent: string;
  backend: Backend;
  browser: string;
  viewport: { width: number; height: number };
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
  /** Characters returned to the agent so far: what the session has cost in tokens, roughly. */
  chars: number;
  approval: Approval | null;
  help: HelpRequest | null;
  dialog: PageDialog | null;
  downloads: { name: string; size: number }[];
  /** Things that happened and deserve a word to the person. Each is shown once, by its id. */
  notices: Notice[];
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
  chars: 0,
  approval: null,
  help: null,
  dialog: null,
  downloads: [],
  notices: [],
  ended: null,
  frame: null,
  settingsVersion: 0,
};

export type Action =
  | { type: 'event'; event: ServerEvent }
  | { type: 'frame'; src: string; at: number }
  | { type: 'connection'; status: ConnectionStatus };

export function reduce(state: ViewerState, action: Action): ViewerState {
  switch (action.type) {
    case 'frame':
      return { ...state, frame: { src: action.src, at: action.at } };
    case 'connection':
      return { ...state, connection: action.status };
    case 'event':
      return applyEvent(state, action.event);
  }
}

function withNotice(state: ViewerState, notice: NewNotice): ViewerState {
  const id = (state.notices.at(-1)?.id ?? 0) + 1;
  return { ...state, notices: [...state.notices, { ...notice, id } as Notice] };
}

function applyEvent(state: ViewerState, event: ServerEvent): ViewerState {
  switch (event.type) {
    case 'session_started':
      return {
        ...initialState,
        connection: state.connection,
        frame: state.frame,
        settingsVersion: state.settingsVersion,
        session: {
          id: event.session,
          agent: event.agent,
          backend: event.backend,
          browser: event.browser,
          viewport: event.viewport,
          startedAt: event.ts,
        },
        control: 'agent',
        controlSince: event.ts,
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
              picture: state.frame?.src,
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
        ended: { reason: event.reason, detail: event.detail, at: event.ts },
      };
  }
}
