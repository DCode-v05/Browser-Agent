// The chat: a person gives the agent its tasks here and reads its answers (spec 9.14).

import { useEffect, useRef, useState, type KeyboardEvent } from 'react';

import type { Chat } from '../state/reducer';
import type { StateView } from '../state/view';
import { W } from '../wording';
import { Icon } from './Icon';
import { Button } from './StatusPanel';
import { richText } from './richText';

/** What the agent is doing, in a word, for the top of the chat. */
export type AgentStatus = 'working' | 'ready' | 'paused' | 'person' | 'waiting' | 'stopped' | 'offline';

export function agentStatus(view: StateView): AgentStatus {
  switch (view.key) {
    case 'ended':
      return 'stopped';
    case 'paused':
      return 'paused';
    case 'person':
      return 'person';
    case 'waiting_approval':
    case 'person_requested':
      return 'waiting';
    case 'agent':
    case 'blocked':
      return view.working || view.key === 'blocked' ? 'working' : 'ready';
    default:
      return 'offline';
  }
}

interface Props {
  chat: Chat;
  status: AgentStatus;
  /** What the agent is doing at this moment, as the timeline says it. */
  doing: string;
  /** False when a task cannot be sent: the session has ended, or the connection is down. */
  open: boolean;
  /** The longest task the service takes. */
  maxChars: number;
  onSend(text: string): void;
}

export function ChatPanel({ chat, status, doing, open, maxChars, onSend }: Props) {
  const [draft, setDraft] = useState('');
  const end = useRef<HTMLDivElement>(null);
  const count = chat.messages.length;

  // The newest message is at the bottom, and it is kept in sight.
  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'nearest' });
  }, [count, chat.working]);

  const task = draft.trim();
  const canSend = open && task.length > 0 && task.length <= maxChars;
  const send = () => {
    if (!canSend) return;
    onSend(task);
    setDraft('');
  };
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter starts a new line. While text is being composed, Enter belongs to that.
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    send();
  };

  return (
    <section className="chat" aria-label={W.chat.title}>
      <div className="chat-head">
        <h3 className="panel-title">{W.chat.title}</h3>
        <span className="agent-status" data-status={status} data-testid="agent-status">
          <span className="agent-status-dot" aria-hidden="true" />
          {W.chat.status[status]}
        </span>
      </div>
      <div className="chat-scroll">
        <div className="chat-messages" role="log" aria-label={W.chat.messages}>
          {count === 0 && <p className="chat-empty">{W.chat.empty}</p>}
          {chat.messages.map((message) => (
            <div key={message.id} className="chat-message" data-role={message.role} data-failed={message.failed || undefined}>
              <span className="chat-who">
                <Icon name={message.role === 'person' ? 'person' : message.failed ? 'alert' : 'agent'} />
                {message.role === 'person' ? W.chat.you : W.chat.agent}
              </span>
              <p className="chat-text">{message.role === 'agent' ? richText(message.text) : message.text}</p>
            </div>
          ))}
          {chat.working && (
            <p className="chat-working" data-status={status} data-testid="chat-working">
              <span className="chat-working-dot" aria-hidden="true" />
              {status === 'working' ? doing || W.chat.working : W.chat.status[status]}
            </p>
          )}
          <div ref={end} />
        </div>
      </div>
      <form
        className="chat-compose"
        onSubmit={(event) => {
          event.preventDefault();
          send();
        }}
      >
        <textarea
          className="chat-input"
          rows={2}
          value={draft}
          maxLength={maxChars}
          disabled={!open}
          placeholder={open ? (chat.working ? W.chat.placeholderWorking : W.chat.placeholder) : W.chat.closed}
          aria-label={W.chat.inputLabel}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKey}
        />
        <Button kind="primary" icon="send" onClick={send} disabled={!canSend} label={W.chat.send}>
          {null}
        </Button>
      </form>
    </section>
  );
}
