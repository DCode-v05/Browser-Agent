import type { Connection } from '../connection/connection';

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
