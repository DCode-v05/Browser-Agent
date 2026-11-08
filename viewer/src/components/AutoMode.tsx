import { useEffect, useRef } from 'react';

import type { ClientCommand } from '../protocol';
import type { AutoInfo, LimitInfo, RefusedStep, TaskInfo } from '../state/reducer';
import { W } from '../wording';
import { Icon } from './Icon';
import { Button } from './StatusPanel';
import { trapTab } from './focus';

const AUTO_NOTICE_KEY = 'bap-browser.auto-notice-accepted';

export function autoNoticeAccepted(): boolean {
  try {
    return localStorage.getItem(AUTO_NOTICE_KEY) === 'true';
  } catch {
    return false;
  }
}

export function acceptAutoNotice(): void {
  try {
    localStorage.setItem(AUTO_NOTICE_KEY, 'true');
  } catch {
  }
}

function modeText(auto: AutoInfo): string {
  if (auto.mode !== 'auto') return W.autoMode.mode[auto.mode];
  switch (auto.state) {
    case 'paused':
      return W.autoMode.mode.auto_paused;
    case 'waiting_for_task':
      return W.autoMode.mode.auto_waiting_for_task;
    case 'unavailable':
      return W.autoMode.mode.auto_unavailable;
    default:
      return W.autoMode.mode.auto;
  }
}

export function ModeChip({ auto, onClick }: { auto: AutoInfo | null; onClick(): void }) {
  if (!auto) return null;
  return (
    <button type="button" className="chip chip-button" data-kind="mode" title={auto.why ?? W.buttons.openSettings} onClick={onClick}>
      {modeText(auto)}
    </button>
  );
}

export function TaskLine({ task, onDrop }: { task: TaskInfo | null; onDrop(host: string): void }) {
  if (!task) return null;
  return (
    <div className="task-line">
      <p className="task-text">{W.autoMode.task.line(task.task)}</p>
      {task.from === 'agent' && <span className="task-by-agent">{W.autoMode.task.byAgent}</span>}
      <div className="site-chips">
        {task.sites.map((site) => {
          const named = site.grade === 'named';
          const description = site.grade === 'added_read' ? W.autoMode.task.site.readOnly(site.host) : W.autoMode.task.site.mayAct(site.host);
          return (
            <span key={site.host} className="site-chip" role="group" aria-label={description} title={description}>
              <span aria-hidden="true">{named ? site.host : `+ ${site.host}`}</span>
              <Button kind="quiet" icon="close" label={W.autoMode.task.drop(site.host)} onClick={() => onDrop(site.host)}>
                {null}
              </Button>
            </span>
          );
        })}
      </div>
    </div>
  );
}

export function FirstTimeNotice({ onAccept, onDismiss }: { onAccept(): void; onDismiss(): void }) {
  const safe = useRef<HTMLButtonElement>(null);
  useEffect(() => safe.current?.focus(), []);
  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && onDismiss()}>
      <div
        className="confirm"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="auto-notice-title"
        aria-describedby="auto-notice-p0 auto-notice-p1"
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Escape') onDismiss();
          trapTab(event);
        }}
      >
        <h2 id="auto-notice-title" className="confirm-question">
          {W.autoMode.notice.title}
        </h2>
        {W.autoMode.notice.body.map((paragraph, index) => (
          <p key={paragraph} id={`auto-notice-p${index}`} className="confirm-consequence">
            {paragraph}
          </p>
        ))}
        <div className="confirm-actions">
          <Button ref={safe} onClick={onDismiss}>
            {W.autoMode.notice.notNow}
          </Button>
          <Button kind="primary" onClick={onAccept}>
            {W.autoMode.notice.turnOn}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function AutoPausedBar({ why, onResume }: { why?: string; onResume(): void }) {
  return (
    <div className="card" data-tone="waiting" role="group" aria-label={W.autoMode.paused.resume}>
      <div className="card-head">
        <Icon name="pause" />
        <span className="card-kind">{W.autoMode.paused.resume}</span>
      </div>
      <p className="card-summary">{W.autoMode.paused.bar(why ?? '')}</p>
      <div className="card-actions">
        <Button kind="primary" hint={W.buttons.hint.resumeAuto} onClick={onResume}>
          {W.autoMode.paused.resume}
        </Button>
      </div>
    </div>
  );
}

export function LimitBar({ limit, onExtend, onEndTask }: { limit: LimitInfo; onExtend(): void; onEndTask(): void }) {
  const text =
    limit.kind === 'calls'
      ? W.autoMode.limit.calls(limit.scope, limit.limit)
      : limit.kind === 'minutes'
        ? W.autoMode.limit.minutes(limit.scope, limit.limit)
        : W.autoMode.limit.spend(limit.scope, `$${limit.limit.toFixed(2)}`);
  return (
    <div className="card" data-tone="waiting" role="group" aria-label={text}>
      <p className="card-summary">{text}</p>
      <div className="card-actions">
        {limit.more !== undefined && (
          <Button kind="primary" hint={W.buttons.hint.allowMore} onClick={onExtend}>
            {W.autoMode.limit.allowMore(limit.more)}
          </Button>
        )}
        <Button hint={W.buttons.hint.endTask} onClick={onEndTask}>
          {W.autoMode.limit.endTask}
        </Button>
      </div>
    </div>
  );
}

export function FlaggedNotice({ site, onClose }: { site: string; onClose(): void }) {
  return (
    <div className="card" data-tone="danger" role="group" aria-label={W.autoMode.flagged.title}>
      <div className="card-head">
        <Icon name="alert" />
        <span className="card-kind">{W.autoMode.flagged.title}</span>
      </div>
      <p className="card-summary">{W.autoMode.flagged.notice(site)}</p>
      <div className="card-actions">
        <Button hint={W.buttons.hint.dismiss} onClick={onClose}>
          {W.buttons.dismiss}
        </Button>
      </div>
    </div>
  );
}

export function RefusedList({ refused, onAllow }: { refused: RefusedStep[]; onAllow(id: string): void }) {
  return (
    <div className="card" role="group" aria-label={W.autoMode.refusedList.title}>
      <div className="card-head">
        <Icon name="blocked" />
        <span className="card-kind">{W.autoMode.refusedList.title}</span>
      </div>
      <ul className="refused-list">
        {refused.map((item) => (
          <li key={item.step} className="refused-item">
            <p className="card-summary">{item.label}</p>
            <p className="card-note">{item.reason}</p>
            {item.id &&
              (item.allowed ? (
                <p className="card-note">{W.autoMode.refusedList.allowed}</p>
              ) : (
                <div className="card-actions">
                  <Button hint={W.buttons.hint.allowRefused} onClick={() => onAllow(item.id!)}>
                    {W.buttons.allowOnce}
                  </Button>
                </div>
              ))}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CheckBars({
  auto,
  limit,
  refused,
  send,
}: {
  auto: AutoInfo | null;
  limit: LimitInfo | null;
  refused: RefusedStep[];
  send(command: ClientCommand): void;
}) {
  return (
    <>
      {auto?.state === 'paused' && <AutoPausedBar why={auto.why} onResume={() => send({ type: 'resume_auto' })} />}
      {limit && <LimitBar limit={limit} onExtend={() => send({ type: 'extend_limit' })} onEndTask={() => send({ type: 'end_task' })} />}
      {refused.length > 0 && <RefusedList refused={refused} onAllow={(id) => send({ type: 'allow_refused', id })} />}
    </>
  );
}
