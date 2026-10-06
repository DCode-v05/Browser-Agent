// The pop-up that asks a person to allow or deny a step the agent may not take by itself (spec 8.2,
// 9.16). It comes up over the page, on every backend, the moment the agent asks.

import { useEffect, useRef } from 'react';

import type { Approval } from '../state/reducer';
import { W } from '../wording';
import { timeLeft } from './Cards';
import { Icon } from './Icon';
import { Button } from './StatusPanel';
import { trapTab } from './focus';

interface Props {
  approval: Approval;
  now: number;
  onAnswer(answer: 'once' | 'site' | 'deny'): void;
  /** The person wants to look at the page first. The request stays open, as a card. */
  onLater(): void;
}

export function ApprovalPopup({ approval, now, onAnswer, onLater }: Props) {
  const box = useRef<HTMLDivElement>(null);
  // The pop-up takes the focus and none of its buttons does: a key pressed for something else, in
  // the moment the pop-up arrives, must not allow anything.
  useEffect(() => box.current?.focus(), [approval.id]);
  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && onLater()}>
      <div
        className="confirm popup"
        role="dialog"
        aria-modal="true"
        aria-labelledby="approval-popup-title"
        aria-describedby="approval-popup-summary"
        tabIndex={-1}
        ref={box}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Escape') onLater();
          trapTab(event);
        }}
      >
        <div className="popup-head">
          <span className="popup-icon" aria-hidden="true">
            <Icon name="approval" size="large" />
          </span>
          <div>
            <p className="popup-kind">{W.approval.title}</p>
            <h2 id="approval-popup-title" className="confirm-question">
              {W.approval.popup.title}
            </h2>
          </div>
        </div>
        <p id="approval-popup-summary" className="popup-reason">
          {approval.summary}
        </p>
        <p className="confirm-consequence">{approval.everyTime ? W.approval.popup.hintEveryTime : W.approval.popup.hint}</p>
        <p className="card-note">{W.approval.left(timeLeft(approval.expiresAt, now))}</p>
        <div className="confirm-actions">
          <Button onClick={onLater}>{W.approval.popup.later}</Button>
          <Button kind="danger" onClick={() => onAnswer('deny')}>
            {W.buttons.deny}
          </Button>
          {!approval.everyTime && <Button onClick={() => onAnswer('site')}>{W.buttons.allowSite}</Button>}
          <Button kind="primary" onClick={() => onAnswer('once')}>
            {W.buttons.allowOnce}
          </Button>
        </div>
      </div>
    </div>
  );
}
