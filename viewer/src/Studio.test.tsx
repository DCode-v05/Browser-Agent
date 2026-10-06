import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { DemoConnection } from './connection/demo';
import { STATES } from './demo/sessions';
import { createDemoSettings } from './demo/settings';
import { DEFAULT_OPTIONS } from './options';
import type { ClientCommand } from './protocol';
import { moodOf, Studio } from './Studio';
import { desktopOpener, factsFrom, hasSession, NO_FACTS, roomsIn, type Room } from './studio/rooms';
import type { SystemsApi } from './systems/api';
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

describe('what the service says of itself when the window opens', () => {
  function answering(...answers: unknown[]) {
    const fetched = vi.fn<(address: string, how?: RequestInit) => Promise<unknown>>();
    for (const answer of answers) fetched.mockResolvedValueOnce(answer);
    vi.stubGlobal('fetch', fetched);
    return fetched;
  }
  afterEach(() => vi.unstubAllGlobals());

  it('is asked once, with the token in a header and never in the address', async () => {
    const fetched = answering({ ok: true, json: async () => ({ rooms: [cloud], desktop: true, settings: true, systems: true }) });
    expect(await factsFrom('http://127.0.0.1:8765/', 'the-token')).toEqual({ rooms: [{ ...cloud, note: undefined, extension: undefined }], desktop: true, settings: true, systems: true });
    expect(fetched).toHaveBeenCalledTimes(1);
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/sessions');
    expect(how).toMatchObject({ headers: { Authorization: 'Bearer the-token' } });
  });

  it('is nothing more than its sessions for a service that has no more', async () => {
    answering({ ok: true, json: async () => ({ sessions: [], desktop: 'yes', settings: 1, systems: 'all' }) });
    expect(await factsFrom('http://127.0.0.1:8765/', 'the-token')).toEqual(NO_FACTS);
    answering({ ok: false });
    expect(await factsFrom('http://127.0.0.1:8765/', 'the-token')).toEqual(NO_FACTS);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    expect(await factsFrom('http://127.0.0.1:8765/', 'the-token')).toEqual(NO_FACTS);
  });

  it('opens the desktop app with the token in a header', async () => {
    const fetched = answering({ ok: true }, { ok: false });
    const open = desktopOpener('http://127.0.0.1:8765/', 'the-token');
    expect(await open()).toBe(true);
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/desktop');
    expect(how).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-token' } });
    // The service refused, or did not answer: the app did not open.
    expect(await open()).toBe(false);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    expect(await open()).toBe(false);
  });
});

describe('the browsers as systems, from the window (spec 9.17)', () => {
  const off: Room = { ...builtIn, state: 'off' };

  function withSystems(rooms: Room[] = [cloud, chrome, builtIn], loadRooms = vi.fn(async () => null as Room[] | null)) {
    const sources = new Map<string, ReturnType<typeof createDemoSettings>>();
    const changed: [string, Record<string, unknown>][] = [];
    const systems: SystemsApi = {
      list: async () => rooms.map((room) => ({ ...room, enabled: room.state !== 'off', model: 'model-a', log: null, records: '/records' })),
      manage: async () => ({ ok: true }),
      log: async () => null,
      evals: async () => null,
      trace: async () => null,
      rate: async () => false,
      check: async () => ({ ok: false, why: 'not now' }),
      settings: (system) => {
        if (!sources.has(system)) {
          const real = createDemoSettings();
          sources.set(system, { ...real, change: async (surface, changes) => (changed.push([system, changes]), real.change(surface, changes)) });
        }
        return sources.get(system)!;
      },
    };
    const user = userEvent.setup();
    render(<Studio rooms={rooms} loadRooms={loadRooms} pollMs={0} systems={systems} connectionFor={() => new DemoConnection(STATES.agent, { pace: 0, startAt: 1000 })} settings={createDemoSettings()} options={options} />);
    return { user, changed, loadRooms };
  }

  it('has no Systems page where the service has no systems', () => {
    open();
    expect(screen.queryByRole('button', { name: W.studio.systems })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: W.studio.view.configuration })).not.toBeInTheDocument();
  });

  it('shows, under each browser’s own tab, the browser itself, how it is set up and what its tasks took', async () => {
    const { user } = withSystems();
    const views = screen.getByRole('tablist', { name: W.studio.views('Cloud browser') });
    expect(within(views).getAllByRole('tab').map((one) => one.textContent)).toEqual([W.studio.view.agent, W.studio.view.configuration, W.studio.view.evaluations]);
    expect(within(views).getByRole('tab', { name: W.studio.view.agent })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('region', { name: 'Browser' })).toBeInTheDocument();

    // Configuration: that browser's card, and no other's, in place of its page.
    await user.click(within(views).getByRole('tab', { name: W.studio.view.configuration }));
    expect((await screen.findAllByRole('article')).map((card) => card.getAttribute('aria-label'))).toEqual(['Cloud browser']);
    expect(screen.getByRole('region', { name: W.systems.configuration })).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: `${W.systems.use}: Cloud browser` })).toBeChecked();
    expect(screen.queryByRole('region', { name: 'Browser' })).not.toBeInTheDocument();

    // The view stays from one browser to the next, so the three are looked at one after the other.
    await user.click(tab(/Built-in browser/));
    expect(screen.getByRole('tablist', { name: W.studio.views('Built-in browser') })).toBeInTheDocument();
    expect((await screen.findAllByRole('article')).map((card) => card.getAttribute('aria-label'))).toEqual(['Built-in browser']);

    await user.click(screen.getByRole('tab', { name: W.studio.view.evaluations }));
    expect(await screen.findByRole('region', { name: W.systems.evaluations })).toBeInTheDocument();
    expect((await screen.findAllByRole('article')).map((card) => card.getAttribute('aria-label'))).toEqual(['Built-in browser']);

    await user.click(screen.getByRole('tab', { name: W.studio.view.agent }));
    expect(await screen.findByRole('region', { name: 'Browser' })).toBeInTheDocument();
    expect(screen.queryByRole('article')).not.toBeInTheDocument();
  });

  it('turns a browser off from under its own tab, and its tab follows at once', async () => {
    const loadRooms = vi.fn(async () => [cloud, chrome, { ...builtIn, state: 'off' }] as Room[] | null);
    const { user, changed } = withSystems([cloud, chrome, builtIn], loadRooms);
    await user.click(tab(/Built-in browser/));
    await user.click(screen.getByRole('tab', { name: W.studio.view.configuration }));
    await user.click(await screen.findByRole('switch', { name: `${W.systems.use}: Built-in browser` }));
    await waitFor(() => expect(changed).toEqual([['builtin', { system_enabled: false }]]));
    await waitFor(() => expect(tab(/Built-in browser/)).toHaveTextContent(W.studio.off.off));
  });

  it('opens the Systems page in place of a browser’s page, and a tab brings the browser back', async () => {
    const { user } = withSystems();
    await user.click(screen.getByRole('button', { name: W.studio.systems }));
    expect(screen.getByRole('region', { name: W.systems.title })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Browser' })).not.toBeInTheDocument();
    // No browser's tab is the chosen one while the Systems page is shown.
    expect(screen.getAllByRole('tab', { selected: true }).map((one) => one.textContent)).toEqual([W.systems.configuration]);
    await user.click(tab(/Cloud browser/));
    expect(screen.queryByRole('region', { name: W.systems.title })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Browser' })).toBeInTheDocument();
  });

  it('says a browser is turned off, on its tab and on its page, and turns it on from there', async () => {
    const loadRooms = vi.fn(async () => [cloud, chrome, builtIn] as Room[] | null);
    const { user, changed } = withSystems([cloud, chrome, off], loadRooms);
    expect(tab(/Built-in browser/)).toHaveTextContent(W.studio.off.off);
    await user.click(tab(/Built-in browser/));
    expect(screen.getByRole('heading', { name: W.studio.turnedOff })).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: 'Browser' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: W.studio.turnOn }));
    await waitFor(() => expect(changed).toEqual([['builtin', { system_enabled: true }]]));
    // The window asks at once where the pages stand now, and the browser's own page is back.
    await waitFor(() => expect(loadRooms).toHaveBeenCalled());
    expect(await screen.findByRole('region', { name: 'Browser' })).toBeInTheDocument();
  });

  it('opens, on a browser’s page, the settings of that browser', async () => {
    const { user, changed } = withSystems();
    await user.click(screen.getByRole('button', { name: W.buttons.openSettings }));
    const dialog = await screen.findByRole('dialog', { name: W.settings.title });
    await user.click(await within(dialog).findByRole('tab', { name: 'Live view' }));
    await user.click(within(dialog).getByRole('switch', { name: 'Show where the agent is acting' }));
    await waitFor(() => expect(changed).toEqual([['cloud', { show_agent_pointer: false }]]));
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
    [{ ...cloud, state: 'off' }, 'off'],
  ] as const)('%o is %s', (room, mood) => {
    expect(moodOf(room)).toBe(mood);
  });

  it('knows which pages have a session', () => {
    expect([cloud, chrome, { ...cloud, state: 'failed' }, { ...cloud, state: 'ended' }, { ...cloud, state: 'off' }].map(hasSession)).toEqual([true, false, false, true, false]);
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
