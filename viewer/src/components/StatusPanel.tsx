// Who is driving, what is happening now, and the controls: stop, pause and take over are always
// one action away (spec 9.1). In split view it is a card; in full view, a bar above the browser.

import { useEffect, useRef, type ReactNode, type Ref } from 'react';

import type { ViewerOptions } from '../options';
import type { ClientCommand } from '../protocol';
import { formatElapsed } from '../state/timeline';
import type { ControlName, StateKey, StateView } from '../state/view';
import { W } from '../wording';
import { Icon, type IconName } from './Icon';
import { trapTab } from './focus';

const STATE_ICON: Record<StateKey, IconName> = {
  no_agent: 'plug',
  agent: 'agent',
  waiting_approval: 'approval',
  person_requested: 'help',
  person: 'person',
  paused: 'pause',
  blocked: 'blocked',
  ended: 'check',
  disconnected: 'alert',
  refused: 'alert',
};

interface ButtonProps {
  kind?: 'plain' | 'primary' | 'person' | 'danger' | 'danger-solid' | 'quiet';
  icon?: IconName;
  onClick(): void;
  children: ReactNode;
  ref?: Ref<HTMLButtonElement>;
  disabled?: boolean;
  label?: string;
  /** Pressed, and not taken hold yet. It keeps the focus, and takes no second press. */
  busy?: boolean;
  /** What pressing it does, shown when the pointer rests on it. */
  hint?: string;
}

export function Button({ kind = 'plain', icon, onClick, children, ref, disabled, label, busy, hint }: ButtonProps) {
  return (
    <button
      type="button"
      className="button"
      data-kind={kind}
      onClick={busy ? undefined : onClick}
      ref={ref}
      disabled={disabled}
      aria-label={label}
      title={hint ?? label}
      // Not `disabled`: a button that is disabled while it has the focus drops the focus.
      aria-busy={busy || undefined}
      aria-disabled={busy || undefined}
    >
      {icon && <Icon name={icon} />}
      {children}
    </button>
  );
}

interface Props {
  view: StateView;
  now: number;
  layout: 'card' | 'bar';
  options: ViewerOptions;
  onCommand(command: ClientCommand): void;
  onStop(): void;
  onHandBack(): void;
  /** The button a person lands on when leaving the live picture. */
  primaryRef: Ref<HTMLButtonElement>;
  stopRef: Ref<HTMLButtonElement>;
  /** The control a person pressed that has not taken hold yet (spec 9.4). */
  working?: ControlName | null;
  /** In full view, the way back to the split view. */
  onShowSplit?(): void;
  /** Where the focus goes when what held it is gone: an answered card, a closed question. */
  titleRef?: Ref<HTMLHeadingElement>;
}

export function StatusPanel({ view, now, layout, options, onCommand, onStop, onHandBack, primaryRef, stopRef, onShowSplit, titleRef, working }: Props) {
  const driving = view.key === 'person';
  const title = driving && layout === 'bar' ? W.takeover.bar : view.status;
  // The reason a session ended is told once, in the summary.
  const detail = view.key === 'ended' ? '' : driving && layout === 'bar' ? W.takeover.release(options.releaseChord) : view.detail;

  const control = (name: ControlName): ReactNode => {
    switch (name) {
      case 'pause':
        return (
          <Button key={name} icon="pause" busy={working === name} hint={W.buttons.hint.pause} onClick={() => onCommand({ type: 'pause' })}>
            {working === name ? W.buttons.pausing : W.buttons.pause}
          </Button>
        );
      case 'resume':
        return (
          <Button key={name} icon="play" kind="primary" busy={working === name} hint={W.buttons.hint.resume} onClick={() => onCommand({ type: 'resume' })}>
            {working === name ? W.buttons.resuming : W.buttons.resume}
          </Button>
        );
      case 'take_over':
        return (
          <Button key={name} icon="hand" busy={working === name} hint={W.buttons.hint.takeOver} onClick={() => onCommand({ type: 'take_over' })}>
            {working === name ? W.buttons.takingOver : W.buttons.takeOver}
          </Button>
        );
      case 'hand_back':
        return (
          <Button key={name} kind="person" busy={working === name} hint={W.buttons.hint.handBack} onClick={onHandBack} ref={primaryRef}>
            {working === name ? W.buttons.handingBack : W.buttons.handBack}
          </Button>
        );
      case 'done':
        return (
          <Button key={name} icon="check" kind="person" hint={W.buttons.hint.done} onClick={() => onCommand({ type: 'done' })} ref={primaryRef}>
            {W.buttons.done}
          </Button>
        );
      case 'could_not':
        return (
          <Button key={name} hint={W.buttons.hint.couldNot} onClick={() => onCommand({ type: 'could_not' })}>
            {W.buttons.couldNot}
          </Button>
        );
      case 'stop':
        return (
          <Button key={name} icon="stop" kind="danger" hint={W.buttons.hint.stop} onClick={onStop} ref={stopRef}>
            {W.buttons.stop}
          </Button>
        );
    }
  };

  return (
    <div className="status" data-tone={view.tone} data-layout={layout} data-state={view.key}>
      <span className="status-icon" aria-hidden="true">
        <Icon name={STATE_ICON[view.key]} size="large" />
      </span>
      <div className="status-text">
        <h2 className="status-title" tabIndex={-1} ref={titleRef}>
          {title}
        </h2>
        {detail && <p className="status-detail">{detail}</p>}
      </div>
      {view.since > 0 && view.key !== 'ended' && view.key !== 'disconnected' && view.key !== 'refused' && (
        <span className="status-time">
          <span className="sr-only">{W.parts.elapsed} </span>
          {formatElapsed(now - view.since)}
        </span>
      )}
      {(view.controls.length > 0 || onShowSplit) && (
        <div className="status-controls">
          {view.controls.map(control)}
          {onShowSplit && !driving && (
            <Button kind="quiet" icon="collapse" onClick={onShowSplit} label={W.buttons.showSplit}>
              {null}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

interface ConfirmProps {
  question: string;
  consequence: string;
  confirm: string;
  cancel: string;
  onConfirm(): void;
  onCancel(): void;
}

/** A question that must be answered before something that cannot be undone. The safe answer has the focus. */
export function Confirm({ question, consequence, confirm, cancel, onConfirm, onCancel }: ConfirmProps) {
  const safe = useRef<HTMLButtonElement>(null);
  useEffect(() => safe.current?.focus(), []);
  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}>
      <div
        className="confirm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-question"
        aria-describedby="confirm-consequence"
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Escape') onCancel();
          trapTab(event);
        }}
      >
        <h2 id="confirm-question" className="confirm-question">
          {question}
        </h2>
        <p id="confirm-consequence" className="confirm-consequence">
          {consequence}
        </p>
        <div className="confirm-actions">
          <Button onClick={onCancel} ref={safe}>
            {cancel}
          </Button>
          <Button kind="danger-solid" onClick={onConfirm}>
            {confirm}
          </Button>
        </div>
      </div>
    </div>
  );
}
