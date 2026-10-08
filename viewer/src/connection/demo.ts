// Plays a recorded session with no service (spec 9.11), and answers the viewer's commands the way
// the service will: it waits at an approval, hands control over, pauses, stops.

import type { ClientCommand, ControlState, ServerEvent, TaskSite } from '../protocol';
import type { Connection, ConnectionHandlers } from './connection';

/** An event as it is recorded: its time is filled in when it is played. */
export type EventDraft = ServerEvent extends infer E ? (E extends ServerEvent ? Omit<E, 'ts' | 'since'> : never) : never;

export interface Beat {
  /** Milliseconds after the previous beat. */
  after: number;
  /** A picture to show, before the event. */
  frame?: string;
  event?: EventDraft;
  /** What follows an approval request, by the person's answer. */
  approval?: { allowed: Beat[]; denied: Beat[] };
  /** What follows a request for help, by the person's answer. `personFrame` is shown once the person starts typing. */
  help?: { done: Beat[]; couldNot: Beat[]; personFrame?: string };
}

export interface RecordedSession {
  name: string;
  beats: Beat[];
  /** Answers given for the person, so a recording can run past a wait by itself. */
  auto?: { approval?: 'allow' | 'deny'; help?: 'done' | 'could_not' };
  /** Commands sent once the recording has played, to reach a state such as paused. */
  commands?: ClientCommand[];
  /** How the connection ends up, for the disconnected state. */
  afterwards?: 'reconnecting';
  /** The picture stops being confirmed as current, for the stale state. */
  stalls?: boolean;
}

export interface DemoOptions {
  /** Real milliseconds per recorded millisecond. 1 is real pace; 0 plays at once. */
  pace?: number;
  /** The session clock's starting time, in seconds. */
  startAt?: number;
  /** Real time in milliseconds. */
  realNow?: () => number;
  /** How often to say the picture is still current, as the service does for a still page. 0 means never. */
  heartbeatMs?: number;
}

const TIMED = new Set<ServerEvent['type']>([
  'session_started',
  'message',
  'task_changed',
  'step_started',
  'approval_requested',
  'help_requested',
  'dialog_opened',
  'download_saved',
  'navigation_blocked',
  'session_ended',
  'picture_current',
  'task_set',
  'task_ended',
  'check_decided',
  'refused_allowed',
  'page_flagged',
  'auto_changed',
  'limit_reached',
  'limit_lifted',
  'questions_unanswered',
]);

type Waiting = { kind: 'approval'; id: string; beat: Beat } | { kind: 'help'; id: string; beat: Beat; personFrameShown: boolean };

export class DemoConnection implements Connection {
  private queue: Beat[] = [];
  private readonly pace: number;
  private readonly realNow: () => number;
  private handlers: ConnectionHandlers | undefined;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private expiry: ReturnType<typeof setTimeout> | undefined;
  private heartbeat: ReturnType<typeof setInterval> | undefined;
  private readonly heartbeatMs: number;
  private waiting: Waiting | null = null;
  private held: 'paused' | 'person' | null = null;
  /** The task's sites, kept so `drop_site` can answer with the rest of them. */
  private sites: TaskSite[] = [];
  /** The picture on screen, which a step that finishes now keeps. */
  private shown: string | undefined;
  private over = false;
  private readonly startAt: number | undefined;
  /** The session clock at the last beat, in seconds, and the real time of that beat. */
  private base = 0;
  private realBase = 0;

  constructor(
    private readonly session: RecordedSession,
    options: DemoOptions = {},
  ) {
    this.pace = options.pace ?? 1;
    this.realNow = options.realNow ?? (() => Date.now());
    this.heartbeatMs = options.heartbeatMs ?? 0;
    this.startAt = options.startAt;
    this.rewind();
  }

  /** Back to the start of the recording, so the connection can be opened again. */
  private rewind(): void {
    this.queue = [...this.session.beats];
    this.waiting = null;
    this.held = null;
    this.sites = [];
    this.shown = undefined;
    this.over = false;
    this.base = this.startAt ?? this.realNow() / 1000;
    this.realBase = this.realNow();
  }

  start(handlers: ConnectionHandlers): void {
    this.rewind();
    this.handlers = handlers;
    handlers.onStatus('connected');
    this.schedule();
    for (const command of this.session.commands ?? []) this.handle(command);
    handlers.onCaughtUp?.();
    if (this.session.afterwards) handlers.onStatus(this.session.afterwards);
    if (this.heartbeatMs && !this.session.stalls && !this.over) {
      this.emit({ type: 'picture_current' });
      this.heartbeat = setInterval(() => this.emit({ type: 'picture_current' }), this.heartbeatMs);
    }
  }

  now(): number {
    return this.base + (this.realNow() - this.realBase) / 1000;
  }

  close(): void {
    this.over = true;
    clearTimeout(this.timer);
    clearTimeout(this.expiry);
    clearInterval(this.heartbeat);
  }

  send(command: ClientCommand): void {
    this.handle(command);
  }

  private handle(command: ClientCommand): void {
    if (this.over) return;
    switch (command.type) {
      case 'approve':
        if (this.waiting?.kind === 'approval' && this.waiting.id === command.id) {
          this.closeApproval(command.scope === 'site' ? 'allowed_site' : 'allowed');
        }
        break;
      case 'deny':
        if (this.waiting?.kind === 'approval' && this.waiting.id === command.id) this.closeApproval('denied');
        break;
      case 'pause':
        if (!this.held && !this.waiting) this.hold('paused');
        break;
      case 'resume':
        if (this.held === 'paused') this.release('agent');
        break;
      case 'take_over':
        if (this.held !== 'person' && this.waiting?.kind !== 'approval') this.hold('person');
        break;
      case 'hand_back':
        // Handing back without an answer leaves a request for help open.
        if (this.held === 'person') this.release(this.waiting?.kind === 'help' ? 'person_requested' : 'agent');
        break;
      case 'done':
        if (this.waiting?.kind === 'help') this.closeHelp('done');
        break;
      case 'could_not':
        if (this.waiting?.kind === 'help') this.closeHelp('could_not');
        break;
      case 'stop':
        this.emit({ type: 'session_ended', reason: 'person' });
        break;
      case 'resume_auto':
        this.emit({ type: 'auto_changed', mode: 'auto', state: 'on' });
        break;
      case 'allow_refused':
        this.emit({ type: 'refused_allowed', id: command.id });
        break;
      case 'extend_limit':
        this.emit({ type: 'limit_lifted' });
        break;
      case 'drop_site':
        this.sites = this.sites.filter((site) => site.host !== command.host);
        this.emit({ type: 'sites_changed', sites: this.sites });
        break;
      case 'end_task':
        this.emit({ type: 'task_ended' });
        this.emit({ type: 'limit_lifted' });
        break;
      case 'key':
      case 'pointer':
        this.showPersonFrame();
        break;
      default:
        break;
    }
  }

  private schedule(): void {
    while (!this.over && !this.held && !this.waiting && this.queue.length) {
      const delay = this.queue[0].after * this.pace;
      if (delay > 0) {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => {
          this.play();
          this.schedule();
        }, delay);
        return;
      }
      this.play();
    }
  }

  private play(): void {
    const beat = this.queue.shift();
    if (!beat || this.over) return;
    // The clock follows the recording, so a recorded gap is a gap whatever the pace.
    this.base = Math.max(this.now(), this.base + beat.after / 1000);
    this.realBase = this.realNow();
    if (beat.frame) this.show(beat.frame, this.base);
    if (!beat.event) return;
    this.emit(beat.event);
    if (beat.event.type === 'approval_requested' && beat.approval) {
      this.waiting = { kind: 'approval', id: beat.event.id, beat };
      this.control('waiting_approval');
      const answer = this.session.auto?.approval;
      if (answer) this.closeApproval(answer === 'allow' ? 'allowed' : 'denied');
      else this.expiry = setTimeout(() => this.closeApproval('expired'), beat.event.expires_in_s * 1000);
    } else if (beat.event.type === 'help_requested' && beat.help) {
      this.waiting = { kind: 'help', id: beat.event.id, beat, personFrameShown: false };
      this.control('person_requested');
      const answer = this.session.auto?.help;
      if (answer) this.closeHelp(answer);
      else this.expiry = setTimeout(() => this.closeHelp('timed_out'), beat.event.expires_in_s * 1000);
    }
  }

  private emit(draft: EventDraft): void {
    const event = (TIMED.has(draft.type) ? { ...draft, ts: this.now() } : draft) as ServerEvent;
    if (event.type === 'task_set' || event.type === 'sites_changed') this.sites = event.sites;
    this.handlers?.onEvent(event, event.type === 'step_finished' ? this.shown : undefined);
    if (event.type === 'session_ended') this.close();
  }

  private show(frame: string, at: number): void {
    this.shown = frame;
    this.handlers?.onFrame(frame, at);
  }

  private control(state: ControlState): void {
    this.handlers?.onEvent({ type: 'control_changed', state, since: this.now() });
  }

  private hold(by: 'paused' | 'person'): void {
    clearTimeout(this.timer);
    this.held = by;
    this.control(by);
  }

  private release(to: ControlState): void {
    this.held = null;
    this.control(to);
    this.schedule();
  }

  private closeApproval(outcome: 'allowed' | 'allowed_site' | 'denied' | 'expired'): void {
    if (this.waiting?.kind !== 'approval') return;
    const { id, beat } = this.waiting;
    clearTimeout(this.expiry);
    this.waiting = null;
    this.emit({ type: 'approval_closed', id, outcome });
    this.control('agent');
    const branch = outcome === 'allowed' || outcome === 'allowed_site' ? beat.approval?.allowed : beat.approval?.denied;
    this.queue.unshift(...(branch ?? []));
    this.schedule();
  }

  private closeHelp(outcome: 'done' | 'could_not' | 'timed_out'): void {
    if (this.waiting?.kind !== 'help') return;
    const { id, beat } = this.waiting;
    clearTimeout(this.expiry);
    this.waiting = null;
    this.held = null;
    this.emit({ type: 'help_closed', id, outcome });
    this.control('agent');
    this.queue.unshift(...((outcome === 'done' ? beat.help?.done : beat.help?.couldNot) ?? []));
    this.schedule();
  }

  /** A recording has no page to type into, so the first key or click shows the recorded result of typing. */
  private showPersonFrame(): void {
    const waiting = this.waiting;
    if (this.held !== 'person' || waiting?.kind !== 'help' || waiting.personFrameShown) return;
    const frame = waiting.beat.help?.personFrame;
    if (!frame) return;
    waiting.personFrameShown = true;
    this.show(frame, this.now());
  }
}
