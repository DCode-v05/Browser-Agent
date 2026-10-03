// Who is driving, what is happening now, and the controls: stop, pause and take over are always
// one action away (spec 9.1). In split view it is a card; in full view, a bar above the browser.

import { useEffect, useRef, type ReactNode, type Ref } from 'react';

import type { ViewerOptions } from '../options';
import type { ClientCommand } from '../protocol';
import { formatElapsed } from '../state/timeline';
import type { ControlName, StateKey, StateView } from '../state/view';
import { W } from '../wording';
import { Icon, type IconName } from './Icon';

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
};

interface ButtonProps {
  kind?: 'plain' | 'primary' | 'person' | 'danger' | 'danger-solid' | 'quiet';
  icon?: IconName;
  onClick(): void;
  children: ReactNode;
  ref?: Ref<HTMLButtonElement>;
  disabled?: boolean;
  label?: string;
}

export function Button({ kind = 'plain', icon, onClick, children, ref, disabled, label }: ButtonProps) {
  return (
    <button type="button" className="button" data-kind={kind} onClick={onClick} ref={ref} disabled={disabled} aria-label={label}>
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
  /** In full view, the way back to the split view. */
  onShowSplit?(): void;
}

export function StatusPanel({ view, now, layout, options, onCommand, onStop, onHandBack, primaryRef, stopRef, onShowSplit }: Props) {
  const driving = view.key === 'person';
  const title = driving && layout === 'bar' ? W.takeover.bar : view.status;
  // The reason a session ended is told once, in the summary.
  const detail = view.key === 'ended' ? '' : driving && layout === 'bar' ? W.takeover.release(options.releaseChord) : view.detail;

  const control = (name: ControlName): ReactNode => {
    switch (name) {
      case 'pause':
        return (
          <Button key={name} icon="pause" onClick={() => onCommand({ type: 'pause' })}>
            {W.buttons.pause}
          </Button>
        );
      case 'resume':
        return (
          <Button key={name} icon="play" kind="primary" onClick={() => onCommand({ type: 'resume' })}>
            {W.buttons.resume}
          </Button>
        );
      case 'take_over':
        return (
          <Button key={name} icon="hand" onClick={() => onCommand({ type: 'take_over' })}>
            {W.buttons.takeOver}
          </Button>
        );
      case 'hand_back':
        return (
          <Button key={name} kind="person" onClick={onHandBack} ref={primaryRef}>
            {W.buttons.handBack}
          </Button>
        );
      case 'done':
        return (
          <Button key={name} icon="check" kind="person" onClick={() => onCommand({ type: 'done' })} ref={primaryRef}>
            {W.buttons.done}
          </Button>
        );
      case 'could_not':
        return (
          <Button key={name} onClick={() => onCommand({ type: 'could_not' })}>
            {W.buttons.couldNot}
          </Button>
        );
      case 'stop':
        return (
          <Button key={name} icon="stop" kind="danger" onClick={onStop} ref={stopRef}>
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
        <h2 className="status-title">{title}</h2>
        {detail && <p className="status-detail">{detail}</p>}
      </div>
      {view.since > 0 && view.key !== 'ended' && view.key !== 'disconnected' && (
        <span className="status-time">
          <span className="sr-only">Elapsed </span>
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
