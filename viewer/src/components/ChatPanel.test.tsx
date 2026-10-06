import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { ServerEvent } from '../protocol';
import { initialState, reduce, type Chat, type ViewerState } from '../state/reducer';
import { describeState } from '../state/view';
import { W } from '../wording';
import { agentStatus, ChatPanel } from './ChatPanel';
import { richText } from './richText';

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

function show(chat: Chat, open = true, doing = '') {
  const onSend = vi.fn();
  render(<ChatPanel chat={chat} status={chat.working ? 'working' : 'ready'} doing={doing} open={open} maxChars={20} onSend={onSend} />);
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
    const { container } = render(<ChatPanel chat={state.chat} status="ready" doing="" open maxChars={20} onSend={() => {}} />);
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

  it('says how to go on once the session has ended', () => {
    render(<ChatPanel chat={{ enabled: true, working: false, messages: [] }} status="stopped" doing="" open={false} maxChars={20} onSend={() => {}} />);
    expect(screen.getByText(W.chat.startAgain)).toBeTruthy();
  });
});

describe('what the agent is doing, in a word', () => {
  const statusOf = (events: ServerEvent[]) => agentStatus(describeState(play(events), T0, 5));
  const works: ServerEvent = { type: 'task_changed', working: true, ts: T0 };

  it('is ready, working, paused, in your hands or stopped', () => {
    expect(statusOf([started])).toBe('ready');
    expect(statusOf([started, works])).toBe('working');
    expect(statusOf([started, works, { type: 'control_changed', state: 'paused', since: T0 }])).toBe('paused');
    expect(statusOf([started, works, { type: 'control_changed', state: 'person', since: T0 }])).toBe('person');
    expect(statusOf([started, works, { type: 'session_ended', reason: 'person', ts: T0 }])).toBe('stopped');
    expect(agentStatus(describeState(initialState, T0, 5))).toBe('offline');
  });

  it('is shown at the top of the chat, with the step under way beside the working dot', () => {
    show({ enabled: true, working: true, messages: [] }, true, 'Opening huggingface.co');
    expect(screen.getByTestId('agent-status').textContent).toBe(W.chat.status.working);
    expect(screen.getByTestId('agent-status').dataset.status).toBe('working');
    expect(screen.getByTestId('chat-working').textContent).toBe('Opening huggingface.co');
  });

  it('colours the browser for the agent only while it works', () => {
    expect(describeState(play([started]), T0, 5)).toMatchObject({ tone: 'neutral', working: false });
    expect(describeState(play([started, works]), T0, 5)).toMatchObject({ tone: 'agent', working: true });
    // A session with no chat has an agent that works for as long as it drives.
    expect(describeState(play([{ ...started, chat: undefined }]), T0, 5)).toMatchObject({ tone: 'agent', working: true });
  });
});

describe("the agent's answer, shown the way it was meant", () => {
  const shown = (text: string) => render(<p>{richText(text)}</p>).container.querySelector('p')!;

  it('makes bold, code and links of what is marked as such', () => {
    const p = shown('I found **google/vit-base** for `image classification`: https://huggingface.co/google/vit-base.');
    expect(p.textContent).toBe('I found google/vit-base for image classification: https://huggingface.co/google/vit-base.');
    expect(p.querySelector('strong')?.textContent).toBe('google/vit-base');
    expect(p.querySelector('code')?.textContent).toBe('image classification');
    const link = p.querySelector('a')!;
    // The full stop ends the sentence, not the address.
    expect(link.getAttribute('href')).toBe('https://huggingface.co/google/vit-base');
    expect(link.target).toBe('_blank');
    expect(link.rel).toBe('noopener noreferrer');
  });

  it('names a link by the words given for it', () => {
    const link = shown('See [the model page](https://huggingface.co/m).').querySelector('a')!;
    expect([link.textContent, link.getAttribute('href')]).toEqual(['the model page', 'https://huggingface.co/m']);
  });

  it('never makes a link of anything but a web address, and never uses HTML as HTML', () => {
    const p = shown('[click](javascript:alert(1)) <img src=x onerror=alert(1)> 2 * 3 * 4');
    expect(p.querySelector('a')).toBeNull();
    expect(p.querySelector('img')).toBeNull();
    expect(p.textContent).toBe('[click](javascript:alert(1)) <img src=x onerror=alert(1)> 2 * 3 * 4');
  });

  it('leaves what a person wrote as it was written', () => {
    const state = play([started, said(1, 'person', '**not bold**')]);
    const { container } = render(<ChatPanel chat={state.chat} status="ready" doing="" open maxChars={20} onSend={() => {}} />);
    expect(container.querySelector('.chat-text strong')).toBeNull();
    expect(container.querySelector('.chat-text')?.textContent).toBe('**not bold**');
  });
});
