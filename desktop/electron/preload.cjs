// The few things the app's shell may ask of the desktop app. The shell is a web page and gets no
// other way into the machine.

'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  /** Called with the app's state now, and again whenever it changes. */
  onState(listener) {
    const heard = (_event, state) => listener(state);
    ipcRenderer.on('state', heard);
    ipcRenderer.send('ready');
    return () => ipcRenderer.removeListener('state', heard);
  },
  /** Where in the window the agent's browser and the chat are to be shown. */
  place(rects) {
    ipcRenderer.send('place', rects);
  },
  /** Back, forward or reload in the agent's browser, or open one of the demo pages there. */
  go(action, page) {
    ipcRenderer.send('go', action, page);
  },
  startAgain() {
    ipcRenderer.send('start-again');
  },
});
