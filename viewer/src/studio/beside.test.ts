// The chat follows the task (spec 22.3.1): when a person gives the agent a task on a real machine,
// the chat is opened beside the screen, so that it is still with them once an app covers the page.

import { describe, expect, it, vi } from 'vitest';

import type { Connection } from '../connection/connection';
import { openingTheChatWithATask } from './beside';

function aConnection(): Connection & { sent: unknown[] } {
  const sent: unknown[] = [];
  return { sent, start: () => undefined, send: (command) => void sent.push(command), now: () => 0, close: () => undefined };
}

describe('the chat follows the task', () => {
  it('is opened when a task is given, and the task is sent as it was', () => {
    const inner = aConnection();
    const open = vi.fn();
    const connection = openingTheChatWithATask(inner, open);

    connection.send({ type: 'task', text: 'Open Safari' });

    expect(open).toHaveBeenCalledTimes(1);
    expect(inner.sent).toEqual([{ type: 'task', text: 'Open Safari' }]);
  });

  it('is not opened for anything else a person does on the page', () => {
    const inner = aConnection();
    const open = vi.fn();
    const connection = openingTheChatWithATask(inner, open);

    connection.send({ type: 'pause' });
    connection.send({ type: 'take_over' });

    expect(open).not.toHaveBeenCalled();
    expect(inner.sent).toHaveLength(2);
  });
});
