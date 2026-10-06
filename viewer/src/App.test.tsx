import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { App, type AppProps } from './App';
import type { Connection, ConnectionHandlers } from './connection/connection';
import { DemoConnection } from './connection/demo';
import { createDemoSettings } from './demo/settings';
import { STATES } from './demo/sessions';
import { DEFAULT_OPTIONS } from './options';
import type { ClientCommand } from './protocol';

function show(name: string, props: Partial<AppProps> = {}) {
  const sent: ClientCommand[] = [];
  const createConnection = () => {
    const connection = new DemoConnection(STATES[name], { pace: 0, startAt: 1000 });
    const send = connection.send.bind(connection);
    connection.send = (command) => {
      sent.push(command);
      send(command);
    };
    return connection;
  };
  const user = userEvent.setup();
  // The on-screen clock stands still in tests; what it shows is checked through the state it is given.
  render(<App createConnection={createConnection} settings={createDemoSettings()} options={{ ...DEFAULT_OPTIONS, tickMs: 0 }} {...props} />);
  return { sent, user };
}

const button = (name: string | RegExp) => screen.getByRole('button', { name });
const noButton = (name: string | RegExp) => expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
const types = (sent: ClientCommand[]) => sent.map((command) => command.type);

describe('what each state shows (spec 9.3)', () => {
  it('no agent yet: says so, and offers no controls', () => {
    show('no_agent');
    expect(screen.getByRole('heading', { name: 'Waiting for an agent to connect' })).toBeInTheDocument();
    expect(screen.getByText('Nothing to show yet')).toBeInTheDocument();
    noButton('Pause');
    noButton('Take over');
    noButton('Stop session');
  });

  it('agent: who is driving in words, what it is doing, and the three controls', () => {
    show('agent');
    const activity = screen.getByRole('region', { name: 'Activity' });
    expect(within(activity).getByRole('heading', { name: 'Agent is working' })).toBeInTheDocument();
    expect(within(activity).getAllByText('Choosing "India" in "Country"').length).toBeGreaterThan(0);
    expect(button('Pause')).toBeEnabled();
    expect(button('Take over')).toBeEnabled();
    expect(button('Stop session')).toBeEnabled();
    const browser = screen.getByRole('region', { name: 'Browser' });
    expect(within(browser).getByText('Agent is working')).toBeInTheDocument();
    expect(within(browser).getByText('Live')).toBeInTheDocument();
  });

  it('the live picture has a text alternative that follows the page', () => {
    show('agent');
    expect(screen.getByRole('img', { name: 'Live browser view: Sign up, https://example.com/signup' })).toBeInTheDocument();
  });

  it('the address and the tabs are shown', () => {
    show('agent');
    expect(screen.getByLabelText('Address')).toHaveTextContent('https://example.com/signup');
    expect(screen.getByRole('tab', { name: 'Sign up', selected: true })).toBeInTheDocument();
  });

  it('waiting for approval: only Stop stays beside the approval card', () => {
    show('waiting_approval');
    expect(screen.getByRole('heading', { name: 'Waiting for your approval' })).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Browser' })).getByText('Paused for approval')).toBeInTheDocument();
    noButton('Pause');
    noButton('Take over');
    expect(button('Stop session')).toBeEnabled();
  });

  it('person requested: the reason, and Take over, Couldn\'t do it, Stop', () => {
    show('person_requested');
    expect(screen.getByRole('heading', { name: 'The agent asked for help' })).toBeInTheDocument();
    expect(screen.getAllByText(/enter the 6-digit code sent to ada@example.com/).length).toBeGreaterThan(0);
    expect(button('Take over')).toBeEnabled();
    expect(button("Couldn't do it")).toBeEnabled();
    expect(button('Stop session')).toBeEnabled();
    noButton('Pause');
  });

  it('person: the takeover bar says nothing typed is recorded, and offers Done and Stop', () => {
    show('person');
    expect(screen.getByText("You're in control. The agent is waiting. Nothing you type is recorded.")).toBeInTheDocument();
    expect(button('Done')).toBeEnabled();
    expect(button("Couldn't do it")).toBeEnabled();
    expect(button('Stop session')).toBeEnabled();
    noButton('Hand back');
  });

  it('what happened before the viewer opened is not popped up again', () => {
    show('person');
    expect(screen.queryByText('Allowed once')).not.toBeInTheDocument();
  });

  it('person, after taking over unasked: Hand back, not Done', () => {
    show('person_unasked');
    expect(button('Hand back')).toBeEnabled();
    noButton('Done');
  });

  it('paused: Resume, Take over, Stop', () => {
    show('paused');
    expect(screen.getByRole('heading', { name: 'Paused' })).toBeInTheDocument();
    expect(button('Resume')).toBeEnabled();
    expect(button('Take over')).toBeEnabled();
    noButton('Pause');
  });

  it('blocked: the reason, what was blocked, and what happens next', () => {
    show('blocked');
    expect(screen.getByRole('heading', { name: 'Blocked: private address' })).toBeInTheDocument();
    expect(screen.getByText('http://10.0.0.5/admin was not opened: private address.')).toBeInTheDocument();
    expect(screen.getByText('The agent was told and can try another way. You can also take over.')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Browser' })).getByText('Blocked')).toBeInTheDocument();
  });

  it('ended: a summary, and no controls', () => {
    show('ended');
    const summary = screen.getByRole('group', { name: 'Session ended' });
    expect(within(summary).getByText('The agent closed it.')).toBeInTheDocument();
    expect(within(summary).getByText('16')).toBeInTheDocument();
    expect(within(summary).getByText('1')).toBeInTheDocument();
    noButton('Pause');
    noButton('Stop session');
  });

  it('disconnected: says so, marks the picture as not live, and hides the controls', () => {
    show('disconnected');
    expect(screen.getByRole('heading', { name: 'Connection lost. Reconnecting…' })).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Browser' })).getAllByText('Not live').length).toBeGreaterThan(0);
    noButton('Pause');
    noButton('Stop session');
  });

  it('stale picture: "Live" becomes how long there has been no new picture', () => {
    show('stale');
    const browser = screen.getByRole('region', { name: 'Browser' });
    expect(within(browser).getByText(/^No new picture for \d+ s$/)).toBeInTheDocument();
    expect(within(browser).queryByText('Live')).not.toBeInTheDocument();
    expect(button('Pause')).toBeEnabled();
  });

  it('a take-over Chrome session shows no picture and says where to look', () => {
    show('own_browser');
    expect(screen.getByText('The agent is working in your own browser. Watch it there; its steps appear here.')).toBeInTheDocument();
    expect(screen.queryByRole('img', { name: /Live browser view/ })).not.toBeInTheDocument();
  });
});

describe('controls', () => {
  it('Pause sends pause and becomes Resume', async () => {
    const { sent, user } = show('agent');
    await user.click(button('Pause'));
    expect(types(sent)).toEqual(['pause']);
    expect(button('Resume')).toBeInTheDocument();
    await user.click(button('Resume'));
    expect(types(sent)).toEqual(['pause', 'resume']);
    expect(button('Pause')).toBeInTheDocument();
  });

  it('Take over hands the browser to the person, full width, and Hand back returns it', async () => {
    const { sent, user } = show('agent');
    await user.click(button('Take over'));
    expect(types(sent)).toEqual(['take_over']);
    expect(screen.getByText("You're in control. The agent is waiting. Nothing you type is recorded.")).toBeInTheDocument();
    expect(document.querySelector('.app')).toHaveAttribute('data-view', 'full');
    await user.click(button('Hand back'));
    expect(types(sent)).toEqual(['take_over', 'hand_back']);
    expect(await screen.findByText('Handed back. The agent will re-read the page.')).toBeInTheDocument();
    expect(document.querySelector('.app')).toHaveAttribute('data-view', 'split');
  });

  it('Stop always asks first', async () => {
    const { sent, user } = show('agent');
    await user.click(button('Stop session'));
    const confirm = screen.getByRole('alertdialog', { name: 'Stop this session?' });
    expect(within(confirm).getByText('The browser will close and the agent will be told.')).toBeInTheDocument();
    expect(sent).toEqual([]);
    await user.click(within(confirm).getByRole('button', { name: 'Keep running' }));
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(sent).toEqual([]);
    await user.click(button('Stop session'));
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Stop session' }));
    expect(types(sent)).toEqual(['stop']);
    expect(screen.getByRole('group', { name: 'Session ended' })).toBeInTheDocument();
    expect(screen.getByText('You stopped it.')).toBeInTheDocument();
  });

  it('answering a request for help: take over, then Done', async () => {
    const { sent, user } = show('person_requested');
    await user.click(button('Take over'));
    await user.click(button('Done'));
    expect(types(sent)).toEqual(['take_over', 'done']);
    expect(await screen.findByText('Done. The agent continues.')).toBeInTheDocument();
  });
});

describe('approval pop-up (spec 9.16)', () => {
  const popup = () => screen.getByRole('dialog', { name: 'The agent needs your approval' });

  it('comes up when the agent asks, and says what and how long is left', () => {
    show('waiting_approval');
    expect(within(popup()).getByText('Upload cv.pdf to example.com')).toBeInTheDocument();
    expect(within(popup()).getByText(/^\d:\d\d left, then this is denied$/)).toBeInTheDocument();
    // The answers are in the pop-up, and are not offered a second time behind it.
    expect(screen.queryByRole('group', { name: 'Approval needed' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Allow once' })).toHaveLength(1);
    expect(within(popup()).getByRole('button', { name: 'Allow on this site' })).toBeInTheDocument();
    expect(within(popup()).getByRole('button', { name: 'Deny' })).toBeInTheDocument();
  });

  it('takes the focus, and none of its buttons does: a stray key allows nothing', async () => {
    const { sent, user } = show('waiting_approval');
    expect(popup()).toHaveFocus();
    await user.keyboard('{Enter}a');
    expect(sent).toEqual([]);
    expect(popup()).toBeInTheDocument();
  });

  it('is answered from the keyboard, and the focus goes to what the session is doing now', async () => {
    const { sent, user } = show('waiting_approval');
    // Look first, Deny, Allow on this site, Allow once.
    await user.tab();
    await user.tab();
    await user.keyboard('{Enter}');
    expect(sent).toEqual([{ type: 'deny', id: 'a1' }]);
    expect(screen.getByRole('heading', { name: 'Agent is working' })).toHaveFocus();
  });

  it('steps aside for a person who wants to look first, and leaves the request open as a card', async () => {
    const { sent, user } = show('waiting_approval');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(sent).toEqual([]);
    expect(within(screen.getByRole('group', { name: 'Approval needed' })).getByRole('button', { name: 'Allow once' })).toBeInTheDocument();
  });
});

describe('approval card', () => {
  it('says what, where and how long is left', async () => {
    const { user } = show('waiting_approval');
    await user.click(button('Look first'));
    const card = screen.getByRole('group', { name: 'Approval needed' });
    expect(within(card).getByText('Upload cv.pdf to example.com')).toBeInTheDocument();
    expect(within(card).getByText(/^\d:\d\d left, then this is denied$/)).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Allow once' })).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Allow on this site' })).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Deny' })).toBeInTheDocument();
  });

  it.each([
    ['Allow once', { type: 'approve', id: 'a1', scope: 'once' }, 'Allowed once'],
    ['Allow on this site', { type: 'approve', id: 'a1', scope: 'site' }, 'Allowed on this site'],
    ['Deny', { type: 'deny', id: 'a1' }, 'Denied'],
  ])('%s sends the answer, closes what asked and confirms it', async (name, command, toast) => {
    // From the pop-up, and from the card of a person who looked first.
    for (const looksFirst of [false, true]) {
      const { sent, user } = show('waiting_approval');
      if (looksFirst) await user.click(button('Look first'));
      await user.click(button(name));
      expect(sent).toEqual([command]);
      expect(screen.queryByRole('group', { name: 'Approval needed' })).not.toBeInTheDocument();
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      expect(await screen.findByText(toast)).toBeInTheDocument();
      cleanup();
    }
  });

  it('does not take the focus; A moves to it', async () => {
    const { user } = show('waiting_approval');
    await user.click(button('Look first'));
    expect(button('Allow once')).not.toHaveFocus();
    await user.keyboard('a');
    expect(button('Allow once')).toHaveFocus();
  });
});

describe('help and dialog cards', () => {
  it('the help card gives the reason, what to do, and the time left', () => {
    show('person_requested');
    const card = screen.getByRole('group', { name: 'Verification needed' });
    expect(within(card).getByText('enter the 6-digit code sent to ada@example.com')).toBeInTheDocument();
    expect(within(card).getByText('Take over, do the step in the browser, then choose Done.')).toBeInTheDocument();
    expect(within(card).getByText(/left, then the agent is told you could not$/)).toBeInTheDocument();
  });

  it('a page dialog is shown as a card, because the picture cannot show it', () => {
    show('dialog');
    const card = screen.getByRole('group', { name: 'The page opened a dialog' });
    expect(within(card).getByText('Sign out of Northfield? Unsaved changes will be lost.')).toBeInTheDocument();
    expect(within(card).getByText('The agent is answering it.')).toBeInTheDocument();
  });
});

describe('timeline', () => {
  it('lists the steps as sentences, newest last in the log', () => {
    show('ended');
    const log = screen.getByRole('log', { name: 'Steps' });
    const rows = within(log).getAllByRole('button');
    expect(rows[0]).toHaveTextContent('Opened example.com/signup');
    expect(rows.at(-1)).toHaveTextContent('Dismissed the dialog "Sign out of Northfield?"');
  });

  it('typed text appears as a character count', () => {
    show('ended');
    const log = screen.getByRole('log', { name: 'Steps' });
    expect(within(log).getByText('Typed 12 characters into "Full name"')).toBeInTheDocument();
    expect(log).not.toHaveTextContent('Ada Lovelace');
  });

  it('collapses consecutive reads, marks a failure in words, and shows idle gaps', () => {
    show('ended');
    const log = screen.getByRole('log', { name: 'Steps' });
    expect(within(log).getByText('2 times')).toBeInTheDocument();
    expect(within(log).getByText('Could not open 10.0.0.5/admin: private address')).toBeInTheDocument();
    expect(within(log).getAllByText('Failed').length).toBe(1);
    expect(within(log).getByText('idle 12 s')).toBeInTheDocument();
  });

  it('shows the counters: steps, time and characters returned to the agent', () => {
    show('ended');
    expect(screen.getByText(/^16 steps · \d+:\d\d · [\d,]+ chars$/)).toBeInTheDocument();
  });

  it('is empty until the agent works', () => {
    show('empty');
    expect(screen.getByText('Steps appear here as the agent works.')).toBeInTheDocument();
  });

  it('a row opens the step drawer with its picture, timing and result', async () => {
    const { user } = show('ended');
    await user.click(screen.getByRole('button', { name: /Typed 12 characters into "Full name"/ }));
    const drawer = screen.getByRole('dialog', { name: 'Step 3' });
    expect(within(drawer).getByRole('img', { name: 'The browser at step 3' })).toBeInTheDocument();
    expect(within(drawer).getByText('9 ms')).toBeInTheDocument();
    expect(within(drawer).getByText('Typed 12 characters into "Full name"')).toBeInTheDocument();
    await user.click(within(drawer).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog', { name: 'Step 3' })).not.toBeInTheDocument();
  });

  it('Up and Down move between rows and Enter opens the drawer', async () => {
    const { user } = show('ended');
    const rows = within(screen.getByRole('log', { name: 'Steps' })).getAllByRole('button');
    rows.at(-1)!.focus();
    await user.keyboard('{ArrowDown}');
    expect(rows.at(-2)).toHaveFocus();
    await user.keyboard('{ArrowUp}');
    expect(rows.at(-1)).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('dialog', { name: 'Step 16' })).toBeInTheDocument();
  });
});

describe('keyboard (spec 9.8)', () => {
  it('P pauses and resumes', async () => {
    const { sent, user } = show('agent');
    await user.keyboard('p');
    await user.keyboard('p');
    expect(types(sent)).toEqual(['pause', 'resume']);
  });

  it('T takes over, only while an agent is driving', async () => {
    const { sent, user } = show('agent');
    await user.keyboard('t');
    await user.keyboard('t');
    expect(types(sent)).toEqual(['take_over']);
  });

  it('F switches between split and full view', async () => {
    const { user } = show('agent');
    await user.keyboard('f');
    expect(document.querySelector('.app')).toHaveAttribute('data-view', 'full');
    await user.keyboard('f');
    expect(document.querySelector('.app')).toHaveAttribute('data-view', 'split');
  });

  it('keys held with a modifier are left to the browser', async () => {
    const { sent, user } = show('agent');
    await user.keyboard('{Control>}p{/Control}');
    expect(sent).toEqual([]);
  });

  it('during takeover, keys pressed in the picture go to the page, not to the viewer', async () => {
    const { sent, user } = show('person_unasked');
    screen.getByRole('img', { name: /Live browser view/ }).focus();
    await user.keyboard('p');
    expect(types(sent)).toEqual(['key', 'key']);
    expect(sent[0]).toMatchObject({ type: 'key', action: 'down', key: 'p' });
  });

  it('a key still held when the picture loses the focus is let go in the page', async () => {
    const { sent, user } = show('person_unasked');
    const picture = screen.getByRole('img', { name: /Live browser view/ });
    picture.focus();
    await user.keyboard('{Shift>}a');
    sent.length = 0;
    // The person switches to another window: the key comes up where the viewer cannot see it.
    act(() => picture.blur());
    expect(sent).toEqual([{ type: 'key', action: 'up', key: 'Shift', code: 'ShiftLeft' }]);
    // Leaving again lets go of nothing twice.
    act(() => picture.focus());
    act(() => picture.blur());
    expect(sent).toHaveLength(1);
  });

  it('the release chord leaves the picture and focuses Hand back', async () => {
    const { user } = show('person_unasked');
    screen.getByRole('img', { name: /Live browser view/ }).focus();
    await user.keyboard('{Control>}{Alt>}{Enter}{/Alt}{/Control}');
    expect(button('Hand back')).toHaveFocus();
  });
});

describe('announcements', () => {
  it('a new action is announced politely', () => {
    show('agent');
    expect(screen.getByTestId('announce-polite')).toHaveTextContent('Choosing "India" in "Country"');
  });

  it('an approval is announced at once, with how to reach it', () => {
    show('waiting_approval');
    expect(screen.getByTestId('announce-assertive')).toHaveTextContent('Approval needed: Upload cv.pdf to example.com. Press A to go to it.');
  });

  it('a request for help is announced at once', () => {
    show('person_requested');
    expect(screen.getByTestId('announce-assertive')).toHaveTextContent('The agent asked for help: enter the 6-digit code sent to ada@example.com');
  });
});

describe('settings', () => {
  async function open(name = 'agent', props: Partial<AppProps> = {}) {
    const shown = show(name, props);
    await shown.user.click(button('Open settings'));
    const dialog = await screen.findByRole('dialog', { name: 'Settings' });
    await within(dialog).findByRole('tab', { name: 'Browser' });
    return { ...shown, dialog };
  }

  it('says so when the service did not answer, so that nobody believes a change was saved', async () => {
    const unreachable = { ...createDemoSettings(), change: async () => Promise.reject(new Error('no answer')) };
    const { user, dialog } = await open('agent', { settings: unreachable });
    await user.click(within(dialog).getByRole('tab', { name: 'Live view' }));
    const pointer = within(dialog).getByRole('switch', { name: 'Show where the agent is acting' });
    await user.click(pointer);
    expect(await within(dialog).findByText('Not saved: the service did not answer. Try again.')).toBeInTheDocument();
    expect(pointer).toBeChecked();
  });

  it('says Saving while the service has not answered, and Saved only once it has', async () => {
    let answer: () => void = () => undefined;
    const answered = new Promise<void>((resolve) => (answer = resolve));
    const real = createDemoSettings();
    const slow = { ...real, change: async (...given: Parameters<typeof real.change>) => answered.then(() => real.change(...given)) };
    const { user, dialog } = await open('agent', { settings: slow });
    await user.click(within(dialog).getByRole('tab', { name: 'Live view' }));
    await user.click(within(dialog).getByRole('switch', { name: 'Show where the agent is acting' }));
    expect(await within(dialog).findByText('Saving…')).toHaveAttribute('role', 'status');
    expect(within(dialog).queryByText('Saved')).not.toBeInTheDocument();
    await act(async () => answer());
    expect(await within(dialog).findByText('Saved')).toBeInTheDocument();
    expect(within(dialog).queryByText('Saving…')).not.toBeInTheDocument();
  });

  it('opens from the top bar, with a group per kind of setting', async () => {
    const { dialog } = await open();
    expect(within(dialog).getAllByRole('tab').map((tab) => tab.textContent)).toEqual(['Browser', 'Approvals', 'Sites', 'Files', 'Privacy', 'Live view', 'Appearance', 'Advanced']);
    expect(within(dialog).getByRole('tab', { name: 'Browser', selected: true })).toBeInTheDocument();
    expect(within(dialog).getByText('Preferred browser')).toBeInTheDocument();
  });

  it('mobile has no Advanced group and no preferred browser', async () => {
    const { dialog } = await open('agent', { surface: 'mobile' });
    expect(within(dialog).queryByRole('tab', { name: 'Advanced' })).not.toBeInTheDocument();
    expect(within(dialog).queryByText('Preferred browser')).not.toBeInTheDocument();
    expect(within(dialog).getByText('Stay signed in to sites')).toBeInTheDocument();
  });

  it('a change is saved as soon as it is made', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('tab', { name: 'Approvals' }));
    await user.click(within(dialog).getByRole('radio', { name: /Every action/ }));
    expect(within(dialog).getByRole('radio', { name: /Every action/ })).toBeChecked();
    expect(await within(dialog).findByText('Saved')).toBeInTheDocument();
  });

  it('a setting that starts a new browser says it applies to the next session', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('switch', { name: 'Stay signed in to sites' }));
    expect(within(dialog).getByRole('switch', { name: 'Stay signed in to sites' })).toBeChecked();
    expect(await within(dialog).findByText('Saved. Applies to the next session.')).toBeInTheDocument();
  });

  it('a locked setting is shown, disabled, with the reason', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('tab', { name: 'Advanced' }));
    const locked = within(dialog).getByRole('switch', { name: 'Let the agent run scripts in pages' });
    expect(locked).toBeDisabled();
    expect(within(dialog).getByText('Set by your organisation')).toBeInTheDocument();
  });

  it('a site list takes one site per line, keeps the organisation\'s entries, and refuses a bad entry in the row', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('tab', { name: 'Sites' }));
    expect(within(dialog).getByText('*.internal.example')).toBeInTheDocument();
    const list = within(dialog).getByRole('textbox', { name: 'Blocked sites' });
    await user.type(list, 'ads.example.com');
    await user.tab();
    expect(await within(dialog).findByText('Saved')).toBeInTheDocument();
    await user.clear(list);
    await user.type(list, 'not a site');
    await user.tab();
    expect(await within(dialog).findByText("That doesn't look like a site. Use a name such as example.com.")).toBeInTheDocument();
  });

  it('clearing browsing data asks first', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('tab', { name: 'Privacy' }));
    await user.click(within(dialog).getByRole('button', { name: 'Clear data' }));
    const confirm = screen.getByRole('alertdialog', { name: 'Clear cookies and site data in the cloud browser?' });
    expect(within(confirm).getByText("You'll be signed out of sites there, and open sessions will end.")).toBeInTheDocument();
    await user.click(within(confirm).getByRole('button', { name: 'Clear data' }));
    expect(await screen.findByText('Browsing data cleared.')).toBeInTheDocument();
  });

  it('colour mode changes the theme at once', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('tab', { name: 'Appearance' }));
    await user.click(within(dialog).getByRole('radio', { name: 'Dark' }));
    await waitFor(() => expect(document.documentElement).toHaveAttribute('data-theme', 'dark'));
    await user.click(within(dialog).getByRole('radio', { name: 'Match system' }));
    await waitFor(() => expect(document.documentElement).not.toHaveAttribute('data-theme'));
  });

  it('about lists the version and what differs from the defaults', async () => {
    const { user, dialog } = await open();
    await user.click(within(dialog).getByRole('tab', { name: 'Advanced' }));
    expect(await within(dialog).findByText('0.1.0')).toBeInTheDocument();
    expect(within(dialog).getByText('safety.block_private_networks')).toBeInTheDocument();
  });

  it('Escape closes it and focus returns to the settings button; the viewer keys are off while it is open', async () => {
    const { sent, user } = await open();
    await user.keyboard('p');
    expect(sent).toEqual([]);
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Settings' })).not.toBeInTheDocument();
    expect(button('Open settings')).toHaveFocus();
  });

  it('an approval that arrives stays reachable: A closes settings and moves to it', async () => {
    const { user } = await open('waiting_approval');
    await user.keyboard('a');
    expect(screen.queryByRole('dialog', { name: 'Settings' })).not.toBeInTheDocument();
    // The settings screen kept the pop-up back. It asks now.
    expect(screen.getByRole('dialog', { name: 'The agent needs your approval' })).toHaveFocus();
  });
});

describe('inside a client', () => {
  it('drops the product name when shown inside another page', () => {
    show('agent', { embedded: true });
    expect(screen.queryByText('bap-browser')).not.toBeInTheDocument();
  });

  it('shows it when on its own', () => {
    show('agent');
    expect(screen.getByText('bap-browser')).toBeInTheDocument();
  });

  it('names the agent and the browser in use', () => {
    show('agent');
    expect(screen.getByText('Claude Code')).toBeInTheDocument();
    expect(screen.getByText('Cloud browser')).toBeInTheDocument();
  });
});

describe('what had already happened when the viewer connected', () => {
  function connect() {
    let handlers: ConnectionHandlers | undefined;
    const connection: Connection = {
      start: (given) => {
        handlers = given;
        given.onStatus('connected');
      },
      send: () => undefined,
      now: () => 1000,
      close: () => undefined,
    };
    const createConnection = () => connection;
    const { container } = render(<App createConnection={createConnection} settings={createDemoSettings()} options={{ ...DEFAULT_OPTIONS, tickMs: 0 }} />);
    return { handlers: () => handlers!, toasts: () => within(container.querySelector<HTMLElement>('.toasts')!) };
  }

  it('is not popped up as new, and what comes after is', () => {
    const { handlers, toasts } = connect();
    act(() => handlers().onEvent({ type: 'download_saved', name: 'old-report.pdf', size: 2048, ts: 990 }));
    expect(toasts().queryByText(/old-report\.pdf/)).not.toBeInTheDocument();
    act(() => handlers().onCaughtUp?.());
    expect(toasts().queryByText(/old-report\.pdf/)).not.toBeInTheDocument();
    act(() => handlers().onEvent({ type: 'download_saved', name: 'new-report.pdf', size: 2048, ts: 1001 }));
    expect(toasts().getByText(/new-report\.pdf/)).toBeInTheDocument();
  });
});

describe('a link that the service refuses', () => {
  it('says what to do instead of promising to reconnect, and offers no controls', () => {
    const connection: Connection = {
      start: (handlers) => handlers.onStatus('refused'),
      send: () => undefined,
      now: () => 1000,
      close: () => undefined,
    };
    const createConnection = () => connection;
    render(<App createConnection={createConnection} settings={createDemoSettings()} options={{ ...DEFAULT_OPTIONS, tickMs: 0 }} />);
    expect(screen.getByRole('heading', { name: "This link can't open the session" })).toBeInTheDocument();
    expect(screen.getAllByText('Open it again from where you started the session.').length).toBeGreaterThan(0);
    expect(screen.getByText('Not connected')).toBeInTheDocument();
    expect(screen.queryByText(/Reconnecting/)).not.toBeInTheDocument();
    noButton('Pause');
    noButton('Stop session');
  });

  it('promises neither a browser nor steps', () => {
    const connection: Connection = {
      start: (handlers) => handlers.onStatus('refused'),
      send: () => undefined,
      now: () => 1000,
      close: () => undefined,
    };
    const createConnection = () => connection;
    render(<App createConnection={createConnection} settings={createDemoSettings()} options={{ ...DEFAULT_OPTIONS, tickMs: 0 }} />);
    expect(screen.getByText('No session to show')).toBeInTheDocument();
    expect(screen.queryByText('When an agent connects, its browser appears here.')).not.toBeInTheDocument();
    expect(screen.queryByText('Steps appear here as the agent works.')).not.toBeInTheDocument();
  });
});

describe('full view keeps what needs a person on screen', () => {
  const fullView = () => expect(document.querySelector('.app')).toHaveAttribute('data-view', 'full');

  it('an approval can be reached with A and answered without leaving full view', async () => {
    const { sent, user } = show('waiting_approval');
    await user.click(button('Look first'));
    await user.keyboard('f');
    fullView();
    expect(screen.getByRole('group', { name: 'Approval needed' })).toBeInTheDocument();
    await user.keyboard('a');
    expect(button('Allow once')).toHaveFocus();
    await user.click(button('Deny'));
    expect(sent).toEqual([{ type: 'deny', id: 'a1' }]);
    fullView();
  });

  it('an approval that arrives while the browser is shown full width appears there', async () => {
    let handlers: ConnectionHandlers | undefined;
    const connection: Connection = {
      start: (given) => {
        handlers = given;
        given.onStatus('connected');
        given.onEvent({ type: 'session_started', session: 'default', agent: 'Agent', backend: 'remote_headless', browser: 'Chromium', viewport: { width: 1280, height: 800 }, ts: 1000 });
        given.onCaughtUp?.();
      },
      send: () => undefined,
      now: () => 1001,
      close: () => undefined,
    };
    const createConnection = () => connection;
    const user = userEvent.setup();
    render(<App createConnection={createConnection} settings={createDemoSettings()} options={{ ...DEFAULT_OPTIONS, tickMs: 0 }} />);
    await user.keyboard('f');
    fullView();
    act(() => {
      handlers!.onEvent({ type: 'approval_requested', id: 'a9', tool: 'browser_upload_file', summary: 'Upload cv.pdf to example.com', site: 'example.com', expires_in_s: 180, ts: 1001 });
      handlers!.onEvent({ type: 'control_changed', state: 'waiting_approval', since: 1001 });
    });
    expect(button('Allow once')).toBeInTheDocument();
    expect(button('Deny')).toBeInTheDocument();
  });

  it('during a takeover that answers a request for help, the request stays on screen', async () => {
    const { user } = show('person_requested');
    await user.click(button('Take over'));
    fullView();
    expect(screen.getByText('enter the 6-digit code sent to ada@example.com')).toBeInTheDocument();
  });

  it('a page dialog is shown in full view too, because the picture cannot show it', async () => {
    const { user } = show('dialog');
    await user.keyboard('f');
    fullView();
    expect(screen.getByRole('group', { name: 'The page opened a dialog' })).toBeInTheDocument();
  });

  it('the summary of an ended session is shown in full view too', async () => {
    const { user } = show('agent');
    await user.keyboard('f');
    await user.click(button('Stop session'));
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Stop session' }));
    expect(screen.getByRole('group', { name: 'Session ended' })).toBeInTheDocument();
  });
});

describe('focus is never left nowhere', () => {
  it('the Stop confirmation keeps Tab inside it', async () => {
    const { user } = show('agent');
    await user.click(button('Stop session'));
    const confirm = screen.getByRole('alertdialog');
    const keep = within(confirm).getByRole('button', { name: 'Keep running' });
    const stop = within(confirm).getByRole('button', { name: 'Stop session' });
    expect(keep).toHaveFocus();
    await user.tab();
    expect(stop).toHaveFocus();
    await user.tab();
    expect(keep).toHaveFocus();
    await user.tab({ shift: true });
    expect(stop).toHaveFocus();
  });

  it('after an approval is answered from the keyboard, focus goes to what the session is doing now', async () => {
    const { user } = show('waiting_approval');
    await user.click(button('Look first'));
    await user.keyboard('a');
    await user.keyboard('{Enter}');
    expect(screen.getByRole('heading', { name: 'Agent is working' })).toHaveFocus();
  });

  it('after Stop is confirmed from the keyboard, focus goes to the ended session', async () => {
    const { user } = show('agent');
    await user.click(button('Stop session'));
    await user.tab();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('heading', { name: 'Session ended' })).toHaveFocus();
  });
});

describe('a site list is not lost by closing the screen', () => {
  async function openSites() {
    const shown = show('agent');
    await shown.user.click(button('Open settings'));
    const dialog = await screen.findByRole('dialog', { name: 'Settings' });
    await shown.user.click(await within(dialog).findByRole('tab', { name: 'Sites' }));
    return { ...shown, dialog };
  }

  it('Escape saves what was typed before it closes', async () => {
    const { user, dialog } = await openSites();
    await user.type(within(dialog).getByRole('textbox', { name: 'Blocked sites' }), 'evil.example');
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Settings' })).not.toBeInTheDocument());
    await user.click(button('Open settings'));
    const again = await screen.findByRole('dialog', { name: 'Settings' });
    await user.click(await within(again).findByRole('tab', { name: 'Sites' }));
    expect(within(again).getByRole('textbox', { name: 'Blocked sites' })).toHaveValue('evil.example');
  });

  it('Escape does not close the screen over an entry that was refused', async () => {
    const { user, dialog } = await openSites();
    const list = within(dialog).getByRole('textbox', { name: 'Blocked sites' });
    await user.type(list, 'not a site');
    await user.keyboard('{Escape}');
    expect(await within(dialog).findByText("That doesn't look like a site. Use a name such as example.com.")).toBeInTheDocument();
    expect(screen.getByRole('dialog', { name: 'Settings' })).toBeInTheDocument();
    expect(list).toHaveValue('not a site');
    expect(list).toHaveFocus();
  });
});

describe("beside a browser that is a window on the person's own screen", () => {
  it('is one conversation: no picture of the browser, the task as it was asked, and the steps it led to', () => {
    show('beside');
    expect(screen.queryByRole('region', { name: 'Browser' })).not.toBeInTheDocument();
    const talk = screen.getByRole('region', { name: 'Chat' });
    const log = within(talk).getByRole('log', { name: 'Messages' });
    expect(within(log).getByText('Check in for booking SK4821, last name Lovelace. Choose a window seat.')).toBeInTheDocument();
    // The steps of the work under way are open, under the task that led to them.
    expect(log.firstElementChild).toHaveTextContent('Check in for booking SK4821');
    expect(within(log).getByRole('button', { name: '3 steps', expanded: true })).toBeInTheDocument();
    expect(within(log).getByText('Opened example.com/checkin')).toBeInTheDocument();
    expect(within(log).getAllByText('Clicking "Find booking" (button)').length).toBeGreaterThan(0);
    expect(within(talk).getByTestId('agent-status')).toHaveTextContent('Working');
    // There is no picture to show full width, and no second list of the steps.
    noButton('Show the browser full width');
    expect(screen.queryByRole('heading', { name: 'Activity' })).not.toBeInTheDocument();
  });

  it('the box to write in holds the controls: stop the task while it runs, send once something is typed', async () => {
    const { sent, user } = show('beside');
    await user.click(button('Stop this task'));
    await user.click(button('Pause'));
    expect(types(sent)).toEqual(['stop_task', 'pause']);
    await user.type(screen.getByRole('textbox', { name: 'Your task' }), 'Then pick a vegetarian meal');
    noButton('Stop this task');
    await user.click(button('Send the task'));
    expect(sent.at(-1)).toEqual({ type: 'task', text: 'Then pick a vegetarian meal' });
  });

  it('a group of steps folds away and opens again, and a step opens its evidence', async () => {
    const { user } = show('beside');
    await user.click(button('3 steps'));
    expect(screen.queryByText('Opened example.com/checkin')).not.toBeInTheDocument();
    await user.click(button('3 steps'));
    await user.click(screen.getByRole('button', { name: /Opened example\.com\/checkin/ }));
    expect(screen.getByRole('dialog', { name: 'Step 1' })).toBeInTheDocument();
  });

  it('taking over keeps the conversation and the way back on screen', async () => {
    const { sent, user } = show('beside');
    await user.click(button('Take over'));
    expect(types(sent)).toEqual(['take_over']);
    expect(screen.getByTestId('agent-status')).toHaveTextContent("You're in control");
    expect(screen.getByRole('region', { name: 'Chat' })).toBeInTheDocument();
    expect(button('Hand back')).toBeEnabled();
  });

  it('ending the whole session is apart from the rest, and still asks first', async () => {
    const { sent, user } = show('beside');
    await user.click(button('Stop session'));
    expect(sent).toEqual([]);
    const question = screen.getByRole('alertdialog');
    await user.click(within(question).getByRole('button', { name: 'Stop session' }));
    expect(types(sent)).toEqual(['stop']);
  });
});
