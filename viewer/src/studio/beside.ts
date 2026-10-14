// The chat follows the task (spec 22.3.1). On a real machine the agent works in the machine's own
// apps, and whichever it opens covers this page. So when a person gives it a task, the chat is opened
// beside the screen, where the next task can be given without coming back here.

import type { Connection } from '../connection/connection';

/** A connection that opens the chat beside the screen whenever a task is sent through it. */
export function openingTheChatWithATask(connection: Connection, open: () => void): Connection {
  return {
    start: (handlers) => connection.start(handlers),
    send: (command) => {
      if (command.type === 'task') open();
      connection.send(command);
    },
    now: () => connection.now(),
    close: () => connection.close(),
  };
}
