// The viewer as one conversation, for when the browser itself is on the person's screen and this
// page sits beside it: in a window of its own, or in the extension's side panel (spec 9.14, 9.15).
// What the person asked, the steps the agent took, what it answered; one box to write in under it.

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode, type Ref } from 'react';

import type { ClientCommand } from '../protocol';
import type { Step, ViewerState } from '../state/reducer';
import { formatDuration } from '../state/timeline';
import { transcript } from '../state/transcript';
import type { ControlName, StateView } from '../state/view';
import { W } from '../wording';
import { agentStatus } from './ChatPanel';
import { Icon } from './Icon';
import { Button } from './StatusPanel';
import { richText } from './richText';

interface Props {
  state: ViewerState;
  view: StateView;
  /** The longest task the service takes. */
  maxChars: number;
  /** The step whose evidence is open. */
  selected: number | null;
  /** The cards that need a person: an approval, a request for help, a blocked page, the summary. */
  cards: ReactNode;
  /** The step's evidence, when one is open. It covers the conversation. */
  drawer: ReactNode;
  onCommand(command: ClientCommand): void;
  onOpenStep(step: number): void;
  onHandBack(): void;
  onStopSession(): void;
  onOpenSettings(): void;
  titleRef?: Ref<HTMLHeadingElement>;
  settingsRef?: Ref<HTMLButtonElement>;
  stopRef?: Ref<HTMLButtonElement>;
}

function StepRows({ steps, selected, onOpen }: { steps: Step[]; selected: number | null; onOpen(step: number): void }) {
  return (
    <ul className="talk-rows">
      {steps.map((step) => (
        <li key={step.n}>
          <button type="button" className="talk-row" data-status={step.status} aria-haspopup="dialog" aria-expanded={selected === step.n} onClick={() => onOpen(step.n)}>
            {step.status === 'running' ? <span className="spinner" aria-hidden="true" /> : <Icon name={step.status === 'failed' ? 'alert' : 'check'} />}
            <span className="talk-row-text">{step.status === 'running' ? step.label : (step.summary ?? step.label)}</span>
            {step.status === 'failed' && <span className="sr-only">{W.timeline.failed}</span>}
            {step.status === 'running' && <span className="sr-only">{W.timeline.running}</span>}
            {step.ms !== undefined && <span className="talk-row-time">{formatDuration(step.ms)}</span>}
          </button>
        </li>
      ))}
    </ul>
  );
}

export function Conversation({ state, view, maxChars, selected, cards, drawer, onCommand, onOpenStep, onHandBack, onStopSession, onOpenSettings, titleRef, settingsRef, stopRef }: Props) {
  const [draft, setDraft] = useState('');
  /** The groups of steps a person opened or closed by hand. The rest follow the work. */
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const end = useRef<HTMLDivElement>(null);

  const status = agentStatus(view);
  const items = transcript(state.chat.messages, state.steps);
  const lastSteps = items.findLast((item) => item.kind === 'steps')?.key;
  const open = state.connection === 'connected' && !state.ended;
  const onATask = state.chat.working && open;
  // The steps of the work under way are shown; those of work that is over fold away.
  const isShown = (key: string) => toggled[key] ?? (key === lastSteps && onATask);
  // A step that is running says what the agent is doing. Between steps it is thinking.
  const newest = items.at(-1);
  const runningInSight = newest?.kind === 'steps' && isShown(newest.key) && newest.steps.at(-1)?.status === 'running';

  // The newest thing is at the bottom, and it is kept in sight.
  const tail = `${items.length}:${state.steps.length}:${state.steps.at(-1)?.status}:${onATask}`;
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'nearest' });
  }, [tail]);

  const task = draft.trim();
  const canSend = open && task.length > 0 && task.length <= maxChars;
  const send = () => {
    if (!canSend) return;
    onCommand({ type: 'task', text: task });
    setDraft('');
  };
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter starts a new line. While text is being composed, Enter belongs to that.
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    send();
  };

  const control = (name: ControlName): ReactNode => {
    switch (name) {
      case 'pause':
        return (
          <Button key={name} kind="quiet" icon="pause" hint={W.buttons.hint.pause} onClick={() => onCommand({ type: 'pause' })}>
            {W.buttons.pause}
          </Button>
        );
      case 'resume':
        return (
          <Button key={name} icon="play" hint={W.buttons.hint.resume} onClick={() => onCommand({ type: 'resume' })}>
            {W.buttons.resume}
          </Button>
        );
      case 'take_over':
        return (
          <Button key={name} kind="quiet" icon="hand" hint={W.buttons.hint.takeOver} onClick={() => onCommand({ type: 'take_over' })}>
            {W.buttons.takeOver}
          </Button>
        );
      case 'hand_back':
        return (
          <Button key={name} kind="person" hint={W.buttons.hint.handBack} onClick={onHandBack}>
            {W.buttons.handBack}
          </Button>
        );
      case 'done':
        return (
          <Button key={name} icon="check" kind="person" hint={W.buttons.hint.done} onClick={() => onCommand({ type: 'done' })}>
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
        // Ending the whole session is in the head of the page, apart from the rest.
        return null;
    }
  };

  return (
    <main className="talk">
      <section className="talk-body" aria-label={W.chat.title} data-status={status}>
      <header className="talk-head">
        <span className="brand-mark" aria-hidden="true" />
        <h1 className="talk-title" tabIndex={-1} ref={titleRef}>
          {W.product}
        </h1>
        <span className="agent-status" data-status={status} data-testid="agent-status">
          <span className="agent-status-dot" aria-hidden="true" />
          {W.chat.status[status]}
        </span>
        <span className="top-bar-space" />
        <Button kind="quiet" icon="settings" onClick={onOpenSettings} ref={settingsRef} label={W.buttons.openSettings}>
          {null}
        </Button>
        {view.controls.includes('stop') && (
          <Button kind="quiet" icon="close" onClick={onStopSession} ref={stopRef} label={W.buttons.stop} hint={W.buttons.hint.stop}>
            {null}
          </Button>
        )}
      </header>

      <div className="talk-scroll">
        <div className="talk-items" role="log" aria-label={W.chat.messages}>
          {items.length === 0 && <p className="talk-empty">{W.chat.empty}</p>}
          {items.map((item) => {
            if (item.kind === 'person') {
              return (
                <p key={item.key} className="talk-person">
                  <span className="sr-only">{W.chat.you}: </span>
                  {item.text}
                </p>
              );
            }
            if (item.kind === 'agent') {
              return (
                <p key={item.key} className="talk-agent" data-failed={item.failed || undefined}>
                  <span className="sr-only">{W.chat.agent}: </span>
                  {item.failed && <Icon name="alert" />}
                  <span>{richText(item.text)}</span>
                </p>
              );
            }
            const shown = isShown(item.key);
            const failed = item.steps.filter((step) => step.status === 'failed').length;
            return (
              <div key={item.key} className="talk-steps">
                <button type="button" className="talk-steps-head" aria-expanded={shown} onClick={() => setToggled((all) => ({ ...all, [item.key]: !shown }))}>
                  <Icon name={shown ? 'collapse' : 'expand'} />
                  {W.timeline.steps(item.steps.length)}
                  {failed > 0 && <span className="talk-steps-failed">{W.chat.stepsFailed(failed)}</span>}
                </button>
                {shown && <StepRows steps={item.steps} selected={selected} onOpen={onOpenStep} />}
              </div>
            );
          })}
          {onATask && !runningInSight && (
            <p className="talk-working" data-status={status} data-testid="chat-working">
              {status === 'working' && <span className="spinner" aria-hidden="true" />}
              {status === 'working' ? W.chat.working : W.chat.status[status]}
            </p>
          )}
          <div ref={end} />
        </div>
      </div>

      <div className="talk-cards">{cards}</div>

      <form
        className="talk-compose"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <textarea
          className="talk-input"
          rows={2}
          value={draft}
          maxLength={maxChars}
          disabled={!open}
          placeholder={open ? (onATask ? W.chat.placeholderWorking : W.chat.placeholder) : W.chat.closed}
          aria-label={W.chat.inputLabel}
          title={W.buttons.hint.task}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKey}
        />
        <div className="talk-actions">
          {view.controls.map(control)}
          <span className="top-bar-space" />
          {onATask && !task ? (
            <Button icon="stop" onClick={() => onCommand({ type: 'stop_task' })} label={W.chat.stopTask} hint={W.buttons.hint.stopTask}>
              {null}
            </Button>
          ) : (
            <Button kind="primary" icon="send" onClick={send} disabled={!canSend} label={W.chat.send} hint={W.buttons.hint.send}>
              {null}
            </Button>
          )}
        </div>
      </form>

      {drawer}
      </section>
    </main>
  );
}
