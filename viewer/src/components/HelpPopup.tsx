// The pop-up that asks a person to do what the agent must not do itself (spec 8.4, 9.16): a sign-in,
// a human check such as a CAPTCHA, a payment, or anything else it asked for. It comes up over the
// page, on every backend, the moment the agent asks.

import { useEffect, useRef } from 'react';

import type { HelpKind } from '../protocol';
import type { HelpRequest } from '../state/reducer';
import { W } from '../wording';
import { timeLeft } from './Cards';
import { Icon, type IconName } from './Icon';
import { Button } from './StatusPanel';
import { trapTab } from './focus';

const KIND_ICON: Record<HelpKind, IconName> = {
  login: 'lock',
  verification: 'approval',
  payment: 'alert',
  other: 'help',
};

interface Props {
  help: HelpRequest;
  now: number;
  /** The browser is a window on the person's own screen: they do the step there, not in a picture here. */
  ownBrowser: boolean;
  onTakeOver(): void;
  onCouldNot(): void;
  /** The person wants to look at the page first. The request stays open, as a card. */
  onLater(): void;
}

export function HelpPopup({ help, now, ownBrowser, onTakeOver, onCouldNot, onLater }: Props) {
  const first = useRef<HTMLButtonElement>(null);
  useEffect(() => first.current?.focus(), [help.id]);
  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && onLater()}>
      <div
        className="confirm popup"
        role="dialog"
        aria-modal="true"
        aria-labelledby="help-popup-title"
        aria-describedby="help-popup-reason"
        data-kind={help.kind}
        onKeyDown={(event) => {
          event.stopPropagation();
          if (event.key === 'Escape') onLater();
          trapTab(event);
        }}
      >
        <div className="popup-head">
          <span className="popup-icon" aria-hidden="true">
            <Icon name={KIND_ICON[help.kind]} size="large" />
          </span>
          <div>
            <p className="popup-kind">{W.help.kind[help.kind]}</p>
            <h2 id="help-popup-title" className="confirm-question">
              {W.help.popup.title[help.kind]}
            </h2>
          </div>
        </div>
        <p id="help-popup-reason" className="popup-reason">
          {help.reason}
        </p>
        <p className="confirm-consequence">{ownBrowser ? W.help.popup.hintOwnBrowser : W.help.popup.hint}</p>
        <p className="card-note">{W.help.left(timeLeft(help.expiresAt, now))}</p>
        <div className="confirm-actions">
          <Button onClick={onLater}>{W.help.popup.later}</Button>
          <Button onClick={onCouldNot}>{W.buttons.couldNot}</Button>
          <Button kind="person" icon="hand" onClick={onTakeOver} ref={first}>
            {ownBrowser ? W.help.popup.doIt : W.buttons.takeOver}
          </Button>
        </div>
      </div>
    </div>
  );
}
