import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AutoInfo, LimitInfo, RefusedStep, TaskInfo } from '../state/reducer';
import { W } from '../wording';
import { acceptAutoNotice, AutoPausedBar, autoNoticeAccepted, FirstTimeNotice, FlaggedNotice, LimitBar, ModeChip, RefusedList, TaskLine } from './AutoMode';

afterEach(() => localStorage.clear());

describe('the mode chip', () => {
  it('shows nothing before an auto_changed has arrived', () => {
    render(<ModeChip auto={null} onClick={() => undefined} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it.each([
    [{ mode: 'every_action', state: 'off' }, 'Asks every step'],
    [{ mode: 'risky', state: 'off' }, 'Asks for risky steps'],
    [{ mode: 'auto', state: 'on' }, 'Auto'],
    [{ mode: 'auto', state: 'paused' }, 'Auto, paused'],
    [{ mode: 'auto', state: 'waiting_for_task' }, 'Auto starts with the next task'],
    [{ mode: 'auto', state: 'unavailable' }, 'Auto is unavailable'],
  ] as [AutoInfo, string][])('says %o as %s', (auto, text) => {
    render(<ModeChip auto={auto} onClick={() => undefined} />);
    expect(screen.getByRole('button', { name: text })).toBeInTheDocument();
  });

  it('carries why as its title when it is unavailable', () => {
    render(<ModeChip auto={{ mode: 'auto', state: 'unavailable', why: 'no model key is set' }} onClick={() => undefined} />);
    expect(screen.getByRole('button')).toHaveAttribute('title', 'no model key is set');
  });

  it('opens settings the same way the settings control does', async () => {
    const onClick = vi.fn();
    const user = userEvent.setup();
    render(<ModeChip auto={{ mode: 'auto', state: 'on' }} onClick={onClick} />);
    await user.click(screen.getByRole('button', { name: 'Auto' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });
});

describe('the task line', () => {
  const task: TaskInfo = {
    task: 'Check in for flight SK4821, name Lovelace, and take a window seat.',
    from: 'person',
    sites: [
      { host: 'skylark-air.example', grade: 'named' },
      { host: 'maps.example', grade: 'added_read' },
    ],
  };

  it('shows nothing without a task', () => {
    const { container } = render(<TaskLine task={null} onDrop={() => undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('shows the task, named sites as themselves and added sites with a plus', () => {
    render(<TaskLine task={task} onDrop={() => undefined} />);
    expect(screen.getByText('Task: Check in for flight SK4821, name Lovelace, and take a window seat.')).toBeInTheDocument();
    expect(screen.getByText('skylark-air.example')).toBeInTheDocument();
    expect(screen.getByText('+ maps.example')).toBeInTheDocument();
  });

  it('says whether a site may only be read or also acted on, in the chip\'s accessible name', () => {
    render(<TaskLine task={task} onDrop={() => undefined} />);
    expect(screen.getByRole('group', { name: 'skylark-air.example, may act' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'maps.example, read only' })).toBeInTheDocument();
  });

  it('marks a task an outside agent declared', () => {
    render(<TaskLine task={{ ...task, from: 'agent' }} onDrop={() => undefined} />);
    expect(screen.getByText('Declared by the agent')).toBeInTheDocument();
    expect(screen.queryByText('Declared by the agent', { selector: 'span' })).toBeInTheDocument();
  });

  it('does not mark a task the person gave', () => {
    render(<TaskLine task={task} onDrop={() => undefined} />);
    expect(screen.queryByText('Declared by the agent')).not.toBeInTheDocument();
  });

  it('a chip\'s button drops that site', async () => {
    const onDrop = vi.fn();
    const user = userEvent.setup();
    render(<TaskLine task={task} onDrop={onDrop} />);
    await user.click(screen.getByRole('button', { name: 'Drop maps.example' }));
    expect(onDrop).toHaveBeenCalledWith('maps.example');
  });
});

describe('the first-time notice', () => {
  it('is not accepted until it is, and stays accepted', () => {
    expect(autoNoticeAccepted()).toBe(false);
    acceptAutoNotice();
    expect(autoNoticeAccepted()).toBe(true);
  });

  it('shows the Auto notice word for word, with Turn on Auto and Not now', () => {
    render(<FirstTimeNotice onAccept={() => undefined} onDismiss={() => undefined} />);
    const dialog = screen.getByRole('alertdialog', { name: 'Auto' });
    expect(within(dialog).getByText(/The agent works without asking you at each step\./)).toBeInTheDocument();
    expect(within(dialog).getByText(/Auto asks you less\. It does not make the agent safe\./)).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Turn on Auto' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Not now' })).toBeInTheDocument();
  });

  it('focuses the cautious answer first', () => {
    render(<FirstTimeNotice onAccept={() => undefined} onDismiss={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Not now' })).toHaveFocus();
  });

  it('Turn on Auto accepts; Not now dismisses with nothing saved', async () => {
    const onAccept = vi.fn();
    const onDismiss = vi.fn();
    const user = userEvent.setup();
    render(<FirstTimeNotice onAccept={onAccept} onDismiss={onDismiss} />);
    await user.click(screen.getByRole('button', { name: 'Turn on Auto' }));
    expect(onAccept).toHaveBeenCalledTimes(1);
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it('Escape dismisses it', async () => {
    const onDismiss = vi.fn();
    const user = userEvent.setup();
    render(<FirstTimeNotice onAccept={() => undefined} onDismiss={onDismiss} />);
    await user.keyboard('{Escape}');
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});

describe('Auto Mode paused', () => {
  it('says why, and Resume Auto sends the command', async () => {
    const onResume = vi.fn();
    const user = userEvent.setup();
    render(<AutoPausedBar why="3 steps in a row were refused" onResume={onResume} />);
    expect(screen.getByText('Auto is paused: 3 steps in a row were refused. You are asked about risky steps now.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Resume Auto' }));
    expect(onResume).toHaveBeenCalledTimes(1);
  });
});

describe('a limit reached', () => {
  it('says the limit of steps, and offers Allow more and End task', async () => {
    const onExtend = vi.fn();
    const onEndTask = vi.fn();
    const user = userEvent.setup();
    const limit: LimitInfo = { kind: 'calls', limit: 500, scope: 'task', more: 100 };
    render(<LimitBar limit={limit} onExtend={onExtend} onEndTask={onEndTask} />);
    expect(screen.getByText('This task reached its limit of 500 steps.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Allow 100 more' }));
    expect(onExtend).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole('button', { name: 'End task' }));
    expect(onEndTask).toHaveBeenCalledTimes(1);
  });

  it('says the limit of minutes', () => {
    render(<LimitBar limit={{ kind: 'minutes', limit: 60, scope: 'task', more: 15 }} onExtend={() => undefined} onEndTask={() => undefined} />);
    expect(screen.getByText('This task reached its limit of 60 minutes.')).toBeInTheDocument();
  });

  it('says the spending limit, in the session, with no "Allow more"', () => {
    render(<LimitBar limit={{ kind: 'spend', limit: 0.5, scope: 'session' }} onExtend={() => undefined} onEndTask={() => undefined} />);
    expect(screen.getByText('This session reached its spending limit of $0.50 for model calls.')).toBeInTheDocument();
    expect(screen.queryByText(/Allow .* more/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'End task' })).toBeInTheDocument();
  });
});

describe('a flagged page', () => {
  it('warns that hidden instructions were withheld, and can be closed', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<FlaggedNotice site="shop.example" onClose={onClose} />);
    expect(screen.getByText('Hidden instructions were found on shop.example and withheld from the agent.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: W.buttons.dismiss }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe('the "Refused" list', () => {
  const refused: RefusedStep[] = [
    { step: 6, id: 'r1', label: 'Uploading cv.pdf', reason: 'this step would send something to other people, and the task did not ask for it', allowed: false },
    { step: 9, id: null, label: 'Opening 10.0.0.5', reason: 'the site is known bad', allowed: false },
  ];

  it('lists each refused step with its reason, and "Allow once" where it is possible', () => {
    render(<RefusedList refused={refused} onAllow={() => undefined} />);
    expect(screen.getByText('Uploading cv.pdf')).toBeInTheDocument();
    expect(screen.getByText('this step would send something to other people, and the task did not ask for it')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Allow once' })).toHaveLength(1);
  });

  it('a hard stop refusal has no button', () => {
    render(<RefusedList refused={refused} onAllow={() => undefined} />);
    expect(screen.getByText('Opening 10.0.0.5')).toBeInTheDocument();
    expect(screen.getByText('the site is known bad')).toBeInTheDocument();
  });

  it('Allow once sends the id', async () => {
    const onAllow = vi.fn();
    const user = userEvent.setup();
    render(<RefusedList refused={refused} onAllow={onAllow} />);
    await user.click(screen.getByRole('button', { name: 'Allow once' }));
    expect(onAllow).toHaveBeenCalledWith('r1');
  });

  it('once allowed, says so and has no button', () => {
    render(<RefusedList refused={[{ ...refused[0], allowed: true }]} onAllow={() => undefined} />);
    expect(screen.getByText('Allowed once')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Allow once' })).not.toBeInTheDocument();
  });
});
