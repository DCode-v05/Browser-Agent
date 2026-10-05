import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ServerEvent } from '../protocol';
import { initialState, reduce, type Chat, type ViewerState } from '../state/reducer';
import { describeState } from '../state/view';
import { W } from '../wording';
import { ChatPanel } from './ChatPanel';

const T0 = 1_759_480_000;

const started: ServerEvent = {
  type: 'session_started',
  session: 'default',
  agent: 'Reference agent',
  backend: 'remote_headless',
  browser: 'Chromium 153',
  viewport: { width: 1280, height: 800 },
  chat: true,
  ts: T0,
};

function play(events: ServerEvent[]): ViewerState {
  const connected = reduce(initialState, { type: 'connection', status: 'connected' });
  return events.reduce((state, event) => reduce(state, { type: 'event', event }), connected);
}

const said = (id: number, role: 'person' | 'agent', text: string, failed?: boolean): ServerEvent => ({ type: 'message', id, role, text, failed, ts: T0 + id });

function show(chat: Chat, open = true) {
  const onSend = vi.fn();
  render(<ChatPanel chat={chat} open={open} maxChars={20} onSend={onSend} />);
  return { onSend, input: screen.getByLabelText(W.chat.inputLabel) as HTMLTextAreaElement, button: screen.getByRole('button', { name: W.chat.send }) as HTMLButtonElement };
}

describe('the chat in the session state', () => {
  it('is there only when the session says so', () => {
    expect(play([started]).chat.enabled).toBe(true);
    expect(play([{ ...started, chat: undefined }]).chat.enabled).toBe(false);
  });

  it('keeps the messages in order and never twice', () => {
    const state = play([started, said(1, 'person', 'Open example.com'), said(2, 'agent', 'It is open.'), said(1, 'person', 'Open example.com')]);
    expect(state.chat.messages.map((message) => [message.role, message.text])).toEqual([
      ['person', 'Open example.com'],
      ['agent', 'It is open.'],
    ]);
  });

  it('knows whether the agent is on a task, and says so in the status', () => {
    const idle = play([started]);
    expect(describeState(idle, T0, 5).status).toBe(W.status.waiting_for_task);
    const working = play([started, { type: 'task_changed', working: true, ts: T0 }]);
    expect(working.chat.working).toBe(true);
    expect(describeState(working, T0, 5).status).toBe(W.status.agent);
    const ended = play([started, { type: 'task_changed', working: true, ts: T0 }, { type: 'session_ended', reason: 'person', ts: T0 }]);
    expect(ended.chat.working).toBe(false);
  });

  it('ignores an event it does not know', () => {
    const state = play([started]);
    expect(reduce(state, { type: 'event', event: { type: 'from_the_future' } as unknown as ServerEvent })).toBe(state);
  });
});

describe('the chat panel (spec 9.14)', () => {
  it('says what to do when nothing has been said yet', () => {
    show({ enabled: true, working: false, messages: [] });
    expect(screen.getByText(W.chat.empty)).toBeTruthy();
  });

  it('shows who said what, and marks an answer that is a failure', () => {
    const state = play([started, said(1, 'person', 'Open example.com'), said(2, 'agent', 'The model could not be reached.', true)]);
    const { container } = render(<ChatPanel chat={state.chat} open maxChars={20} onSend={() => {}} />);
    const messages = Array.from(container.querySelectorAll<HTMLElement>('.chat-message'));
    expect(messages.map((message) => [message.dataset.role, message.dataset.failed, message.querySelector('.chat-text')?.textContent])).toEqual([
      ['person', undefined, 'Open example.com'],
      ['agent', 'true', 'The model could not be reached.'],
    ]);
  });

  it('sends the task with Enter and empties the box', () => {
    const { onSend, input } = show({ enabled: true, working: false, messages: [] });
    fireEvent.change(input, { target: { value: '  Find the price  ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).toHaveBeenCalledWith('Find the price');
    expect(input.value).toBe('');
  });

  it('starts a new line with Shift+Enter, and sends with the button', () => {
    const { onSend, input, button } = show({ enabled: true, working: false, messages: [] });
    fireEvent.change(input, { target: { value: 'Line one' } });
    fireEvent.keyDown(input, { key: 'Enter', shiftKey: true });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(button);
    expect(onSend).toHaveBeenCalledWith('Line one');
  });

  it('sends nothing that is empty', () => {
    const { onSend, input, button } = show({ enabled: true, working: false, messages: [] });
    expect(button.disabled).toBe(true);
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSend).not.toHaveBeenCalled();
  });

  it('says the agent is working, and still takes the next task', () => {
    const { input } = show({ enabled: true, working: true, messages: [] });
    expect(screen.getByTestId('chat-working').textContent).toBe(W.chat.working);
    expect(input.disabled).toBe(false);
    expect(input.placeholder).toBe(W.chat.placeholderWorking);
  });

  it('takes nothing once the session has ended', () => {
    const { input, button } = show({ enabled: true, working: false, messages: [] }, false);
    expect(input.disabled).toBe(true);
    expect(button.disabled).toBe(true);
    expect(input.placeholder).toBe(W.chat.closed);
  });
});
