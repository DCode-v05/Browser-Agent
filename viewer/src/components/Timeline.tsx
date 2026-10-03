// The session's steps: one sentence per row, newest on top, with a drawer of evidence behind each
// row (spec 9.1: every step has a picture and its result).

import { useEffect, useRef, type KeyboardEvent } from 'react';

import type { ViewerOptions } from '../options';
import type { Step, ViewerState } from '../state/reducer';
import { buildRows, formatCount, formatDuration, formatElapsed, type Row } from '../state/timeline';
import { W } from '../wording';
import { Icon } from './Icon';
import { Button } from './StatusPanel';
import { trapTab } from './focus';

interface Props {
  state: ViewerState;
  now: number;
  options: ViewerOptions;
  selected: number | null;
  onOpen(step: number): void;
}

export function Timeline({ state, now, options, selected, onOpen }: Props) {
  const rows = buildRows(state.steps, options.idleDividerS);
  const stepRows = rows.filter((row): row is Extract<Row, { kind: 'step' }> => row.kind === 'step');
  const newest = stepRows.at(-1)?.step.n;
  const started = state.session?.startedAt ?? now;
  const elapsed = (state.ended?.at ?? now) - started;

  // The newest row is on top. Down moves to an older row, which is the one before it in the log.
  const move = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button.row'));
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (index < 0) return;
    event.preventDefault();
    buttons[index + (event.key === 'ArrowDown' ? -1 : 1)]?.focus();
  };

  return (
    <section className="timeline">
      <h3 className="panel-title">{W.timeline.title}</h3>
      <div className="rows-scroll">
      <div className="rows" role="log" aria-label="Steps" onKeyDown={move}>
        {rows.map((row) =>
          row.kind === 'idle' ? (
            <div key={row.key} className="idle" role="separator">
              {W.timeline.idle(row.seconds)}
            </div>
          ) : (
            <button
              key={row.key}
              type="button"
              className="row"
              data-status={row.status}
              aria-haspopup="dialog"
              aria-expanded={selected === row.step.n}
              // One stop in the tab order; the arrow keys move between rows.
              tabIndex={row.step.n === newest ? 0 : -1}
              onClick={() => onOpen(row.step.n)}
            >
              <span className="row-number">{row.steps[0].n}</span>
              <span className="row-body">
                <span className="row-text">{row.text}</span>
                {row.count > 1 && <span className="row-count">{W.timeline.times(row.count)}</span>}
              </span>
              {row.status === 'failed' && (
                <span className="row-flag" data-kind="failed">
                  <Icon name="alert" />
                  {W.timeline.failed}
                </span>
              )}
              {row.status === 'running' ? (
                <span className="row-flag" data-kind="running">
                  {W.timeline.running}
                </span>
              ) : (
                row.ms !== undefined && <span className="row-time">{formatDuration(row.ms)}</span>
              )}
            </button>
          ),
        )}
      </div>
      </div>
      {rows.length === 0 && <p className="timeline-empty">{W.timeline.empty}</p>}
      {state.session && (
        <p className="counters">{W.timeline.counters(W.timeline.steps(state.steps.length), formatElapsed(elapsed), W.timeline.chars(formatCount(state.chars)))}</p>
      )}
    </section>
  );
}

interface DrawerProps {
  step: Step;
  viewport: { width: number; height: number };
  onClose(): void;
}

export function StepDrawer({ step, viewport, onClose }: DrawerProps) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => close.current?.focus(), [step.n]);
  const facts: [string, string][] = [];
  if (step.ms !== undefined) facts.push([W.drawer.took, formatDuration(step.ms)]);
  if (step.chars !== undefined) facts.push([W.drawer.returned, W.timeline.chars(formatCount(step.chars))]);
  if (step.url) facts.push([W.drawer.address, step.url]);

  return (
    <div
      className="drawer"
      role="dialog"
      aria-label={W.drawer.title(step.n)}
      onKeyDown={(event) => {
        event.stopPropagation();
        if (event.key === 'Escape') onClose();
        trapTab(event);
      }}
    >
      <div className="drawer-head">
        <h3 className="drawer-title">{W.drawer.title(step.n)}</h3>
        <span className="drawer-tool">{step.tool}</span>
        <Button kind="quiet" icon="close" onClick={onClose} ref={close} label={W.buttons.close}>
          {null}
        </Button>
      </div>
      <div className="drawer-body">
        {step.picture ? (
          <div className="drawer-picture">
            <img src={step.picture} alt={W.drawer.pictureAlt(step.n)} />
            {step.target && (
              <span
                className="target"
                aria-hidden="true"
                style={{
                  left: `${(step.target.x / viewport.width) * 100}%`,
                  top: `${(step.target.y / viewport.height) * 100}%`,
                  width: `${(step.target.w / viewport.width) * 100}%`,
                  height: `${(step.target.h / viewport.height) * 100}%`,
                }}
              />
            )}
          </div>
        ) : (
          <p className="drawer-none">{W.drawer.noPicture}</p>
        )}
        <dl className="facts">
          {facts.map(([name, value]) => (
            <div key={name} className="fact">
              <dt>{name}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        <p className="drawer-label">{W.drawer.result}</p>
        <p className="drawer-result" data-status={step.status}>
          {step.summary ?? step.label}
        </p>
      </div>
    </div>
  );
}
