import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { DemoConnection } from './connection/demo';
import { STATES } from './demo/sessions';
import { createDemoSettings } from './demo/settings';
import { DEFAULT_OPTIONS } from './options';
import type { ClientCommand } from './protocol';
import { moodOf, Studio } from './Studio';
import { desktopFrom, hasSession, roomsIn, type Room } from './studio/rooms';
import { W } from './wording';

const cloud: Room = { id: 'cloud', backend: 'remote_headless', state: 'agent', attention: false, working: false };
const chrome: Room = { id: 'chrome', backend: 'takeover_chrome', state: 'waiting', attention: false, working: false, extension: '/home/ada/.bap-browser/extension' };
const builtIn: Room = { id: 'builtin', backend: 'bundled_chromium', state: 'agent', attention: false, working: false };
const options = { ...DEFAULT_OPTIONS, tickMs: 0 };

function open(rooms: Room[] = [cloud, chrome, builtIn], loadRooms = vi.fn(async () => null as Room[] | null), pollMs = 0) {
  const asked: string[] = [];
  const pages: string[] = [];
  const user = userEvent.setup();
  render(
    <Studio
      rooms={rooms}
      loadRooms={loadRooms}
      pollMs={pollMs}
      connectionFor={(room) => {
        asked.push(room);
        return new DemoConnection(STATES.agent, { pace: 0, startAt: 1000 });
      }}
      onPage={(room) => pages.push(room)}
      settings={createDemoSettings()}
      options={options}
    />,
  );
  return { asked, pages, user, loadRooms };
}

const tab = (name: RegExp) => screen.getByRole('tab', { name });

describe('the window of three pages (spec 9.16)', () => {
  it('has a page for each browser, and opens on the first', () => {
    const { asked } = open();
    const tabs = within(screen.getByRole('tablist', { name: W.studio.pages })).getAllByRole('tab');
    expect(tabs.map((one) => one.textContent)).toEqual(['Cloud browserReady', 'My ChromeNot connected', 'Built-in browserReady']);
    expect(tab(/Cloud browser/)).toHaveAttribute('aria-selected', 'true');
    // The page under the tabs is that browser's own session.
    expect(asked).toEqual(['cloud']);
    expect(screen.getByRole('region', { name: 'Browser' })).toBeInTheDocument();
  });

  it('shows another page with its own session when its tab is pressed', async () => {
    const { asked, pages, user } = open();
    await user.click(tab(/Built-in browser/));
    expect(tab(/Built-in browser/)).toHaveAttribute('aria-selected', 'true');
    expect(asked).toEqual(['cloud', 'builtin']);
    expect(pages).toEqual(['builtin']);
  });

  it('says how to connect a Chrome that is not there yet, and opens no session for it', async () => {
    const { asked, user } = open();
    await user.click(tab(/My Chrome/));
    expect(screen.getByRole('heading', { name: W.studio.connect.title })).toBeInTheDocument();
    expect(screen.getByText('/home/ada/.bap-browser/extension')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Browser' })).not.toBeInTheDocument();
    expect(asked).toEqual(['cloud']);
  });

  it('says why a browser could not be started', async () => {
    const failed: Room = { ...builtIn, state: 'failed', note: 'The browser could not be started: it is not installed' };
    const { user } = open([cloud, chrome, failed]);
    expect(tab(/Built-in browser/)).toHaveTextContent(W.studio.off.failed);
    await user.click(tab(/Built-in browser/));
    expect(screen.getByRole('heading', { name: W.studio.failed })).toBeInTheDocument();
    expect(screen.getByText(/it is not installed/)).toBeInTheDocument();
  });

  it('opens on the page the person was on', () => {
    render(<Studio rooms={[cloud, chrome, builtIn]} loadRooms={async () => null} pollMs={0} opensOn="builtin" connectionFor={() => new DemoConnection(STATES.agent, { pace: 0, startAt: 1000 })} settings={createDemoSettings()} options={options} />);
    expect(tab(/Built-in browser/)).toHaveAttribute('aria-selected', 'true');
  });

  it('keeps asking where the pages stand, and marks one that needs the person', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const loadRooms = vi.fn(async () => [cloud, { ...chrome, state: 'agent' }, { ...builtIn, state: 'person_requested', attention: true }] as Room[] | null);
      open([cloud, chrome, builtIn], loadRooms, 1500);
      expect(tab(/Built-in browser/)).toHaveAttribute('data-mood', 'ready');
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1600);
      });
      await waitFor(() => expect(tab(/Built-in browser/)).toHaveAttribute('data-mood', 'attention'));
      expect(tab(/Built-in browser/)).toHaveTextContent(W.studio.mood.attention);
      // The Chrome that has connected is a page like the others now.
      expect(tab(/My Chrome/)).toHaveTextContent(W.studio.mood.ready);
      // An answer that could not be had changes nothing.
      loadRooms.mockResolvedValueOnce(null);
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1600);
      });
      expect(tab(/Built-in browser/)).toHaveAttribute('data-mood', 'attention');
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('the button that opens the desktop app (spec 9.16)', () => {
  function withApp(openDesktop?: () => Promise<boolean>) {
    const user = userEvent.setup();
    render(<Studio rooms={[cloud, chrome, builtIn]} loadRooms={async () => null} pollMs={0} openDesktop={openDesktop} connectionFor={() => new DemoConnection(STATES.agent, { pace: 0, startAt: 1000 })} settings={createDemoSettings()} options={options} />);
    return user;
  }

  it('is not there when the service has no app to open', () => {
    withApp();
    expect(screen.queryByRole('button', { name: W.studio.desktop.open })).not.toBeInTheDocument();
  });

  it('asks the service to open the app, and says it is open', async () => {
    const openDesktop = vi.fn(async () => true);
    const user = withApp(openDesktop);
    await user.click(screen.getByRole('button', { name: W.studio.desktop.open }));
    expect(openDesktop).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(W.studio.desktop.opened)).toHaveAttribute('role', 'status');
  });

  it('says so when the app could not be opened, and can be pressed again', async () => {
    const user = withApp(async () => false);
    await user.click(screen.getByRole('button', { name: W.studio.desktop.open }));
    expect(await screen.findByText(W.studio.desktop.failed)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: W.studio.desktop.open })).toBeEnabled();
  });
});

describe('asking the service for the desktop app', () => {
  async function asked(first: unknown, second = { ok: true }) {
    const fetched = vi.fn<(address: string, how?: RequestInit) => Promise<unknown>>();
    fetched.mockResolvedValueOnce({ ok: true, json: async () => first }).mockResolvedValue(second);
    vi.stubGlobal('fetch', fetched);
    try {
      const open = await desktopFrom('http://127.0.0.1:8765/', 'the-token');
      return { open, opened: open ? await open() : null, calls: fetched.mock.calls };
    } finally {
      vi.unstubAllGlobals();
    }
  }

  it('gives no way to open an app the service does not have', async () => {
    expect((await asked({ rooms: [] })).open).toBeNull();
    expect((await asked({ rooms: [], desktop: false })).open).toBeNull();
    expect((await asked({ rooms: [], desktop: 'yes' })).open).toBeNull();
  });

  it('asks with the token in a header, never in the address', async () => {
    const { opened, calls } = await asked({ rooms: [], desktop: true });
    expect(opened).toBe(true);
    const [address, how] = calls[1];
    expect(address).toBe('http://127.0.0.1:8765/api/desktop');
    expect(how).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-token' } });
  });

  it('says the app did not open when the service refused', async () => {
    expect((await asked({ rooms: [], desktop: true }, { ok: false })).opened).toBe(false);
  });
});

describe('where a page stands, in a word', () => {
  it.each([
    [{ ...cloud, working: true }, 'working'],
    [cloud, 'ready'],
    [{ ...cloud, state: 'paused' }, 'paused'],
    [{ ...cloud, state: 'person' }, 'person'],
    [{ ...cloud, state: 'ended' }, 'stopped'],
    [{ ...cloud, state: 'person_requested', attention: true }, 'attention'],
    [chrome, 'off'],
    [{ ...cloud, state: 'starting' }, 'off'],
  ] as const)('%o is %s', (room, mood) => {
    expect(moodOf(room)).toBe(mood);
  });

  it('knows which pages have a session', () => {
    expect([cloud, chrome, { ...cloud, state: 'failed' }, { ...cloud, state: 'ended' }].map(hasSession)).toEqual([true, false, false, true]);
  });
});

describe('what the service says of its pages', () => {
  it('is read with care: it comes from outside', () => {
    expect(roomsIn({ rooms: [cloud, { id: 7 }, { id: 'x', backend: 'my_fridge', state: 'agent' }, null] })).toEqual([{ ...cloud, note: undefined, extension: undefined }]);
  });

  it('is nothing for a service with one session', () => {
    expect(roomsIn({ sessions: [{ id: 'default', state: 'agent' }] })).toBeNull();
    expect(roomsIn({ rooms: [] })).toBeNull();
    expect(roomsIn('not an answer')).toBeNull();
  });
});

describe('the pop-up that asks a person to do a step (spec 9.16)', () => {
  function ask() {
    const sent: ClientCommand[] = [];
    const user = userEvent.setup();
    render(
      <App
        createConnection={() => {
          const connection = new DemoConnection(STATES.person_requested, { pace: 0, startAt: 1000 });
          const send = connection.send.bind(connection);
          connection.send = (command) => {
            sent.push(command);
            send(command);
          };
          return connection;
        }}
        settings={createDemoSettings()}
        options={options}
      />,
    );
    return { sent, user, popup: screen.getByRole('dialog') };
  }

  it('comes up when the agent asks, says what it needs, and has the focus on the way to do it', () => {
    const { popup } = ask();
    expect(within(popup).getByRole('heading')).toHaveTextContent(/^The agent needs/);
    expect(within(popup).getByText(W.help.popup.hint)).toBeInTheDocument();
    expect(within(popup).getByRole('button', { name: W.buttons.takeOver })).toHaveFocus();
    // The answers are in the pop-up, and are not offered a second time behind it.
    expect(screen.getAllByRole('button', { name: W.buttons.takeOver })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: W.buttons.couldNot })).toHaveLength(1);
  });

  it('takes over from the pop-up', async () => {
    const { sent, user, popup } = ask();
    await user.click(within(popup).getByRole('button', { name: W.buttons.takeOver }));
    expect(sent.map((command) => command.type)).toEqual(['take_over']);
  });

  it('tells the agent the person could not', async () => {
    const { sent, user, popup } = ask();
    await user.click(within(popup).getByRole('button', { name: W.buttons.couldNot }));
    expect(sent.map((command) => command.type)).toEqual(['could_not']);
  });

  it('steps aside for a person who wants to look first, and leaves the request open', async () => {
    const { sent, user } = ask();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(sent).toEqual([]);
    // The request is still there to answer, where it was before there were pop-ups.
    expect(screen.getByRole('button', { name: W.buttons.takeOver })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: W.buttons.couldNot })).toBeInTheDocument();
  });
});
