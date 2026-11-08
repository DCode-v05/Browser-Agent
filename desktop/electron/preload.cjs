'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('desktop', {
  onState(listener) {
    const heard = (_event, state) => listener(state);
    ipcRenderer.on('state', heard);
    ipcRenderer.send('ready');
    return () => ipcRenderer.removeListener('state', heard);
  },
  place(rects) {
    ipcRenderer.send('place', rects);
  },
  go(action, page) {
    ipcRenderer.send('go', action, page);
  },
  startAgain() {
    ipcRenderer.send('start-again');
  },
  show(page) {
    ipcRenderer.send('show', page);
  },
  theme(dark) {
    ipcRenderer.send('theme', dark);
  },
});
