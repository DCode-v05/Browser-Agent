'use strict';

const { app, BrowserWindow, screen, shell } = require('electron');

const { placedAtTheSide, chatOf, widthOf } = require('./side-place.cjs');

const width = widthOf(process.env.BAP_SIDE_CHAT_WIDTH);
const address = chatOf(process.env.BAP_SIDE_CHAT ?? '');

if (!address || !width) {
  process.stderr.write(
    'error: BAP_SIDE_CHAT must be the address of a page\'s chat alone, and BAP_SIDE_CHAT_WIDTH its width.\n',
  );
  app.exit(2);
} else {
  app.whenReady().then(() => {
    const room = screen.getPrimaryDisplay().workArea;
    const win = new BrowserWindow({
      ...placedAtTheSide(room, width),
      title: 'bap-browser chat',
      alwaysOnTop: true,
      fullscreenable: false,
      maximizable: false,
      webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false },
    });
    win.setAlwaysOnTop(true, 'floating');
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    win.webContents.setWindowOpenHandler(({ url }) => {
      if (/^https?:/.test(url)) void shell.openExternal(url);
      return { action: 'deny' };
    });
    win.webContents.on('will-navigate', (event, url) => {
      if (new URL(url).origin !== new URL(address).origin) event.preventDefault();
    });
    win.webContents.on('did-finish-load', () => {
      const at = win.getBounds();
      process.stdout.write(`The chat's window is open at ${at.x}, ${at.y}, ${at.width} by ${at.height}; shown: ${win.isVisible()}; above the other apps: ${win.isAlwaysOnTop()}; page: ${win.webContents.getTitle()}\n`);
    });
    win.webContents.on('did-fail-load', (event, code, description) => {
      process.stderr.write(`error: the chat could not be loaded: ${description}\n`);
    });
    void win.loadURL(address);
  });
  app.on('window-all-closed', () => app.quit());
}
