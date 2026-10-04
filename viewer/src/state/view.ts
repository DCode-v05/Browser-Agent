// What each state looks like (spec 9.3): the status line, the border and label of the live
// picture, the controls on offer, and how urgently a change is announced.

import { W } from '../wording';
import type { ViewerState } from './reducer';

export type StateKey =
  | 'no_agent'
  | 'agent'
  | 'waiting_approval'
  | 'person_requested'
  | 'person'
  | 'paused'
  | 'blocked'
  | 'ended'
  | 'disconnected'
  | 'refused';

export type Tone = 'none' | 'agent' | 'person' | 'waiting' | 'neutral' | 'danger';
export type ControlName = 'pause' | 'resume' | 'take_over' | 'hand_back' | 'done' | 'could_not' | 'stop';
export type FrameState = 'connecting' | 'live' | 'stale' | 'paused' | 'person' | 'ended' | 'disconnected' | 'own_browser' | 'empty';

export interface StateView {
  key: StateKey;
  status: string;
  /** The current action, the reason for a request, or why the session ended. */
  detail: string;
  tone: Tone;
  label: string;
  controls: ControlName[];
  urgency: 'polite' | 'assertive';
  frame: FrameState;
  /** When the session started, for the elapsed time. Zero when there is no session. */
  since: number;
}

function currentAction(state: ViewerState): string {
  const last = state.steps.at(-1);
  if (!last) return '';
  return last.status === 'running' ? last.label : (last.summary ?? last.label);
}

function frameState(state: ViewerState, key: StateKey, now: number, staleAfterS: number): FrameState {
  if (key === 'refused') return state.frame ? 'disconnected' : 'empty';
  if (key === 'disconnected') return 'disconnected';
  if (key === 'ended') return 'ended';
  if (key === 'no_agent') return 'empty';
  if (state.session?.backend === 'takeover_chrome') return 'own_browser';
  if (!state.frame) return 'connecting';
  if (key === 'person') return 'person';
  if (key === 'paused') return 'paused';
  // Only a picture that should be moving can be stale.
  if ((key === 'agent' || key === 'blocked') && now - state.frame.at > staleAfterS) return 'stale';
  return 'live';
}

export function describeState(state: ViewerState, now: number, staleAfterS: number): StateView {
  const since = state.session?.startedAt ?? 0;
  const finish = (view: Omit<StateView, 'frame' | 'since'>): StateView => ({
    ...view,
    since,
    frame: frameState(state, view.key, now, staleAfterS),
  });

  if (state.connection === 'refused') {
    return finish({ key: 'refused', status: W.status.refused, detail: W.refused, tone: 'none', label: W.label.disconnected, controls: [], urgency: 'assertive' });
  }
  if (!state.session) {
    return finish({ key: 'no_agent', status: W.status.no_agent, detail: '', tone: 'none', label: '', controls: [], urgency: 'polite' });
  }
  // Once a session has ended there is nothing live to lose, so its summary stays whatever the connection does.
  if (state.ended) {
    return finish({
      key: 'ended',
      status: W.status.ended,
      detail: state.ended.detail ?? W.ended[state.ended.reason],
      tone: 'none',
      label: '',
      controls: [],
      urgency: 'polite',
    });
  }
  if (state.connection !== 'connected') {
    return finish({ key: 'disconnected', status: W.status.disconnected, detail: '', tone: 'none', label: W.label.disconnected, controls: [], urgency: 'assertive' });
  }

  switch (state.control) {
    case 'waiting_approval':
      return finish({
        key: 'waiting_approval',
        status: W.status.waiting_approval,
        detail: state.approval?.summary ?? '',
        tone: 'waiting',
        label: W.label.waiting_approval,
        controls: ['stop'],
        urgency: 'assertive',
      });
    case 'person_requested':
      return finish({
        key: 'person_requested',
        status: W.status.person_requested,
        detail: state.help?.reason ?? '',
        tone: 'waiting',
        label: W.label.person_requested,
        controls: ['take_over', 'could_not', 'stop'],
        urgency: 'assertive',
      });
    case 'person':
      return finish({
        key: 'person',
        status: W.status.person,
        detail: state.help?.reason ?? '',
        tone: 'person',
        label: W.label.person,
        // "Done" answers a request for help. Without one, the person simply hands back.
        controls: state.help ? ['done', 'could_not', 'stop'] : ['hand_back', 'stop'],
        urgency: 'assertive',
      });
    case 'paused':
      return finish({
        key: 'paused',
        status: W.status.paused,
        detail: currentAction(state),
        tone: 'neutral',
        label: W.label.paused,
        controls: ['resume', 'take_over', 'stop'],
        urgency: 'polite',
      });
    default:
      break;
  }

  if (state.blocked) {
    return finish({
      key: 'blocked',
      status: W.status.blocked(state.blocked.reason),
      detail: state.blocked.url,
      tone: 'danger',
      label: W.label.blocked,
      controls: ['take_over', 'stop'],
      urgency: 'assertive',
    });
  }
  return finish({
    key: 'agent',
    status: W.status.agent,
    detail: currentAction(state),
    tone: 'agent',
    label: W.label.agent,
    controls: ['pause', 'take_over', 'stop'],
    urgency: 'polite',
  });
}
