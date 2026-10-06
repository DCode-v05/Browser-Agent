// The cards pinned above the timeline: an approval, a request for help, a page dialog, a blocked
// page, and the summary when a session ends. Each asks rarely and clearly (spec 9.1).

import type { Ref } from 'react';

import type { Approval, HelpRequest, PageDialog, ViewerState } from '../state/reducer';
import { formatCount, formatElapsed } from '../state/timeline';
import { W } from '../wording';
import { Icon } from './Icon';
import { Button } from './StatusPanel';

export function timeLeft(expiresAt: number, now: number): string {
  return formatElapsed(Math.max(0, Math.ceil(expiresAt - now)));
}

interface ApprovalProps {
  approval: Approval;
  now: number;
  onAnswer(answer: 'once' | 'site' | 'deny'): void;
  /** Where the A key lands. The card never takes the focus by itself. */
  firstRef: Ref<HTMLButtonElement>;
}

export function ApprovalCard({ approval, now, onAnswer, firstRef }: ApprovalProps) {
  return (
    <div className="card" data-tone="waiting" role="group" aria-label={W.approval.title}>
      <div className="card-head">
        <Icon name="approval" />
        <span className="card-kind">{W.approval.title}</span>
      </div>
      <p className="card-summary">{approval.summary}</p>
      <p className="card-note">{W.approval.left(timeLeft(approval.expiresAt, now))}</p>
      <div className="card-actions">
        <Button kind="primary" onClick={() => onAnswer('once')} ref={firstRef}>
          {W.buttons.allowOnce}
        </Button>
        {!approval.everyTime && <Button onClick={() => onAnswer('site')}>{W.buttons.allowSite}</Button>}
        <Button kind="danger" onClick={() => onAnswer('deny')}>
          {W.buttons.deny}
        </Button>
      </div>
    </div>
  );
}

export function HelpCard({ help, now, cardRef }: { help: HelpRequest; now: number; cardRef: Ref<HTMLDivElement> }) {
  return (
    <div className="card" data-tone="waiting" role="group" aria-label={W.help.kind[help.kind]} tabIndex={-1} ref={cardRef}>
      <div className="card-head">
        <Icon name="help" />
        <span className="card-kind">{W.help.kind[help.kind]}</span>
      </div>
      <p className="card-summary">{help.reason}</p>
      <p className="card-note">{W.help.hint}</p>
      <p className="card-note">{W.help.left(timeLeft(help.expiresAt, now))}</p>
    </div>
  );
}

export function DialogCard({ dialog }: { dialog: PageDialog }) {
  return (
    <div className="card" data-tone="neutral" role="group" aria-label={W.dialog.title}>
      <div className="card-head">
        <Icon name="dialog" />
        <span className="card-kind">{W.dialog.title}</span>
        <span className="card-tag">{W.dialog.kind[dialog.kind]}</span>
      </div>
      <p className="card-summary">{dialog.text}</p>
      <p className="card-note">{W.dialog.waiting}</p>
    </div>
  );
}

export function BlockedNotice({ url, reason }: { url: string; reason: string }) {
  return (
    <div className="card" data-tone="danger" role="group" aria-label={W.notice.blockedTitle}>
      <div className="card-head">
        <Icon name="blocked" />
        <span className="card-kind">{W.notice.blockedTitle}</span>
      </div>
      <p className="card-summary card-breakable">{W.notice.blockedBody(url, reason)}</p>
      <p className="card-note">{W.notice.blockedNext}</p>
    </div>
  );
}

/** An approval that was denied because nobody was watching stays until the person has seen it. */
export function UnwatchedNotice({ onDismiss }: { onDismiss(): void }) {
  return (
    <div className="card" data-tone="waiting" role="group" aria-label={W.approval.title}>
      <p className="card-summary">{W.approval.outcome.unwatched}</p>
      <div className="card-actions">
        <Button onClick={onDismiss}>{W.buttons.dismiss}</Button>
      </div>
    </div>
  );
}

export function SummaryCard({ state, onNewSession }: { state: ViewerState; onNewSession?(): void }) {
  if (!state.ended || !state.session) return null;
  const facts: [string, string][] = [
    [W.summary.steps, formatCount(state.steps.length)],
    [W.summary.time, formatElapsed(state.ended.at - state.session.startedAt)],
    [W.summary.files, formatCount(state.downloads.length)],
    [W.summary.chars, W.timeline.chars(formatCount(state.chars))],
  ];
  return (
    <div className="card summary" data-tone={state.ended.reason === 'failed' ? 'danger' : 'neutral'} role="group" aria-label={W.summary.title}>
      <p className="card-summary">{state.ended.detail ?? W.ended[state.ended.reason]}</p>
      <dl className="facts">
        {facts.map(([name, value]) => (
          <div key={name} className="fact">
            <dt>{name}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {onNewSession && state.session.restartable && (
        <div className="card-actions">
          <Button kind="primary" icon="play" onClick={onNewSession}>
            {W.buttons.newSession}
          </Button>
        </div>
      )}
    </div>
  );
}
