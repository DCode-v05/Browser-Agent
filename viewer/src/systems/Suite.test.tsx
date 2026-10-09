// The task sets of a browser (spec 12.7): a person starts a run, sees where it is, stops it, and
// reads how it went.

import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { SetName, SuiteAnswer, SuiteOverall, SuiteRun, SuiteTotals, SystemsApi } from './api';
import { headline, ParityCard, SuiteCard } from './Suite';
import { W } from '../wording';

const NONE: SuiteTotals = {
  tasks: 0,
  trials: 0,
  passed: 0,
  pass_rate: null,
  every_time: 0,
  every_time_rate: null,
  ask_recall: null,
  needless_asks: null,
  attacks: 0,
  attacks_followed: 0,
  attack_rate: null,
  attacks_asked: 0,
  input_tokens: 0,
  output_tokens: 0,
  cost_usd: null,
};

function run(set: SetName, totals: Partial<SuiteTotals>, more: Partial<SuiteRun> = {}): SuiteRun {
  return { id: 'r1', set, mode: 'agent', model: 'gpt-test', started: 1_791_400_000, duration_ms: 125_000, trials: 3, stopped: false, of: 2, tasks: [], totals: { ...NONE, ...totals }, ...more };
}

const SHORT = run(
  'short',
  { tasks: 2, trials: 6, passed: 5, pass_rate: 0.833, every_time: 1, every_time_rate: 0.5, input_tokens: 41_000, output_tokens: 900, cost_usd: 0.12 },
  {
    tasks: [
      { id: 'a', title: 'Put one product in the basket', risky: null, passed: 3, trials: [1, 2, 3].map(() => ({ passed: true, why: '', asked: 0, attacked: null, outcome: 'answered', steps: 2, ms: 900 })) },
      {
        id: 'b',
        title: 'Order what is in the basket',
        risky: null,
        passed: 2,
        trials: [
          { passed: true, why: '', asked: 1, attacked: null, outcome: 'answered', steps: 4, ms: 900 },
          { passed: true, why: '', asked: 1, attacked: null, outcome: 'answered', steps: 4, ms: 900 },
          { passed: false, why: 'orders.length is 0', asked: 0, attacked: null, outcome: 'answered', steps: 2, ms: 900 },
        ],
      },
    ],
  },
);

function suiteOf(over: Partial<SuiteAnswer> = {}): SuiteAnswer {
  return {
    system: 'cloud',
    model: 'gpt-test',
    sets: [
      { id: 'short', title: 'Short tasks', lead: 'Whether the agent finishes a small task.', tasks: 20, last: null, earlier: [] },
      { id: 'attack', title: 'Planted instructions', lead: 'Whether planted text is followed.', tasks: 10, last: null, earlier: [] },
    ],
    running: null,
    trials: 3,
    max_trials: 10,
    ...over,
  };
}

function shown(first: SuiteAnswer, over: Partial<SystemsApi> = {}) {
  let now = first;
  const api = {
    suite: vi.fn(async () => now),
    runSuite: vi.fn(async (_system: string, set: SetName, trials: number, mode: 'agent' | 'reference') => {
      now = { ...now, running: { set, mode, trials, tasks: 20, task: 0, trial: 0, title: '', started: 1, stopping: false } };
      return { ok: true, result: now } as const;
    }),
    stopSuite: vi.fn(async () => {
      now = { ...now, running: now.running && { ...now.running, stopping: true } };
      return { ok: true, result: now } as const;
    }),
    ...over,
  } as unknown as SystemsApi;
  render(<SuiteCard system="cloud" api={api} />);
  return { api, user: userEvent.setup(), tell: (next: SuiteAnswer) => (now = next) };
}

const block = async (name: string) => screen.findByRole('listitem', { name });

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('the task sets of a browser', () => {
  it('lists each set with what it measures, and says when none was run', async () => {
    shown(suiteOf());
    const short = await block('Short tasks');
    expect(within(short).getByText('20 tasks')).toBeInTheDocument();
    expect(within(short).getByText('Whether the agent finishes a small task.')).toBeInTheDocument();
    expect(within(short).getByText('This set has not been run yet.')).toBeInTheDocument();
    // Both ways of running it say what they do and what they cost.
    expect(within(short).getByRole('button', { name: 'Run with the agent' })).toHaveAttribute('title', expect.stringContaining('uses tokens'));
    expect(within(short).getByRole('button', { name: 'Run the reference solutions' })).toHaveAttribute('title', expect.stringContaining('no model'));
    expect(within(short).queryByRole('button', { name: 'Show the tasks' })).not.toBeInTheDocument();
  });

  it('starts a run with the times a person chose, and shows where it is', async () => {
    const { api, user } = shown(suiteOf());
    await block('Short tasks');
    await user.selectOptions(screen.getByLabelText('Times each task is tried'), '5');
    await user.click(within(await block('Short tasks')).getByRole('button', { name: 'Run the reference solutions' }));
    expect(api.runSuite).toHaveBeenCalledWith('cloud', 'short', 5, 'reference');
    const short = await block('Short tasks');
    expect(within(short).getByRole('status')).toHaveTextContent('Starting…');
    // While it runs, no other run can be started, on this set or another.
    expect(within(short).queryByRole('button', { name: 'Run with the agent' })).not.toBeInTheDocument();
    expect(within(await block('Planted instructions')).getByRole('button', { name: 'Run with the agent' })).toBeDisabled();
    expect(screen.getByLabelText('Times each task is tried')).toBeDisabled();
  });

  it('follows a run under way, and shows its result when it has ended', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const running = suiteOf({ running: { set: 'short', mode: 'agent', trials: 3, tasks: 20, task: 4, trial: 2, title: 'Find the cheapest product', started: 1, stopping: false } });
    const { api, tell } = shown(running);
    expect(within(await block('Short tasks')).getByRole('status')).toHaveTextContent('Task 4 of 20, try 2 of 3: Find the cheapest product');
    tell(suiteOf({ sets: [{ ...suiteOf().sets[0], last: SHORT, earlier: [{ started: 1, mode: 'agent', pass_rate: 0.7, attack_rate: null }] }] }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1600);
    });
    const short = await block('Short tasks');
    expect(within(short).getByText('Passed 5 of 6 tries (83%).')).toBeInTheDocument();
    expect(within(short).getByText(/Done by the agent, .* each task 3 times, in 2 min 5 s\. Model gpt-test\. 1 of 2 tasks passed every time\. 41,000 tokens in, 900 out\. Cost \$0\.1200\./)).toBeInTheDocument();
    expect(within(short).getByText('Runs before it: 70%.')).toBeInTheDocument();
    const asked = (api.suite as ReturnType<typeof vi.fn>).mock.calls.length;
    // A run that has ended is not asked about any more.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect((api.suite as ReturnType<typeof vi.fn>).mock.calls.length).toBe(asked);
  });

  it('stops a run', async () => {
    const running = suiteOf({ running: { set: 'short', mode: 'agent', trials: 1, tasks: 20, task: 2, trial: 1, title: 'Read a price', started: 1, stopping: false } });
    const { api, user } = shown(running);
    await user.click(within(await block('Short tasks')).getByRole('button', { name: 'Stop the run' }));
    expect(api.stopSuite).toHaveBeenCalledWith('cloud');
    const short = await block('Short tasks');
    expect(within(short).getByRole('status')).toHaveTextContent('Stopping after this task…');
    expect(within(short).getByRole('button', { name: 'Stop the run' })).toBeDisabled();
  });

  it('says why a run could not be started', async () => {
    const busy = 'This browser is busy. Run the task set when its task is finished.';
    const { user } = shown(suiteOf(), { runSuite: vi.fn(async () => ({ ok: false, why: busy }) as const) });
    await user.click(within(await block('Short tasks')).getByRole('button', { name: 'Run with the agent' }));
    expect(await screen.findByText(busy)).toBeInTheDocument();
    expect(within(await block('Short tasks')).getByRole('button', { name: 'Run with the agent' })).toBeEnabled();
  });

  it('shows each task of the newest run, and why one did not pass', async () => {
    const { user } = shown(suiteOf({ sets: [{ ...suiteOf().sets[0], last: SHORT, earlier: [] }] }));
    const short = await block('Short tasks');
    await user.click(within(short).getByRole('button', { name: 'Show the tasks' }));
    const rows = within(within(short).getByRole('table')).getAllByRole('row');
    expect(rows.map((row) => row.textContent)).toEqual([
      'TaskPassedAsked a personStepsWhy it did not pass',
      'Put one product in the basket3 of 30 of 32',
      'Order what is in the basket2 of 32 of 33orders.length is 0',
    ]);
    await user.click(within(short).getByRole('button', { name: 'Hide the tasks' }));
    expect(within(short).queryByRole('table')).not.toBeInTheDocument();
  });

  it('says that the service cannot be reached', async () => {
    shown(suiteOf(), { suite: vi.fn(async () => null) });
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('The service did not answer. Try again.'));
  });
});

describe('what a run came to', () => {
  it('a set of tasks: how many tries passed', () => {
    expect(headline('long', { ...NONE, trials: 4, passed: 4, pass_rate: 1 })).toEqual({ text: 'Passed 4 of 4 tries (100%).', tone: 'success' });
    expect(headline('short', { ...NONE, trials: 4, passed: 3, pass_rate: 0.75 }).tone).toBe('danger');
  });

  it('asking before risky steps: how often a person was asked, with and without need', () => {
    const told = headline('confirm', { ...NONE, ask_recall: 1, needless_asks: 0.25 });
    expect(told).toEqual({ text: 'A person was asked before 100% of the risky steps, and before 25% of the harmless ones.', tone: 'success' });
    expect(headline('confirm', { ...NONE, ask_recall: 0.5, needless_asks: 0 }).tone).toBe('danger');
  });

  it('planted instructions: how many were followed, where fewer is better', () => {
    expect(headline('attack', { ...NONE, attacks: 10, attacks_followed: 2, attack_rate: 0.2 })).toEqual({ text: 'Followed 2 of 10 planted instructions (20%).', tone: 'danger' });
    expect(headline('attack', { ...NONE, attacks: 10, attacks_followed: 0, attack_rate: 0 }).tone).toBe('success');
  });
});

describe('the task sets, browser by browser', () => {
  const overall: SuiteOverall = {
    sets: [
      { id: 'short', title: 'Short tasks', lead: '', tasks: 20 },
      { id: 'attack', title: 'Planted instructions', lead: '', tasks: 10 },
    ],
    systems: [
      { system: 'cloud', runs: { short: { ...NONE, pass_rate: 0.9, mode: 'agent', started: 1_791_400_000, trials: 3, stopped: false }, attack: { ...NONE, attack_rate: 0.2, mode: 'agent', started: 1_791_400_000, trials: 1, stopped: false } } },
      { system: 'builtin', runs: { short: { ...NONE, pass_rate: 1, mode: 'reference', started: 1_791_400_000, trials: 1, stopped: false } } },
    ],
  };
  const names: Record<string, string> = { cloud: 'Cloud browser', builtin: 'Built-in browser' };

  it('puts the newest run of each set on each browser side by side', () => {
    render(<ParityCard overall={overall} nameOf={(id) => names[id]} onRefresh={() => undefined} />);
    const rows = within(screen.getByRole('table')).getAllByRole('row');
    expect(within(rows[0]).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Task set', 'Cloud browser', 'Built-in browser']);
    expect(within(rows[1]).getByRole('rowheader')).toHaveTextContent('Short tasks');
    const [cloud, builtIn] = within(rows[1]).getAllByRole('cell');
    expect(cloud).toHaveTextContent('90% passed');
    expect(cloud).toHaveTextContent('Done by the agent');
    expect(builtIn).toHaveTextContent('100% passed');
    expect(builtIn).toHaveTextContent('Done by the reference solutions');
    const [attacked, notRun] = within(rows[2]).getAllByRole('cell');
    expect(attacked).toHaveTextContent('20% followed');
    expect(notRun).toHaveTextContent('Not run');
  });

  it('says so when nothing was run, and asks again when told to', async () => {
    const onRefresh = vi.fn();
    render(<ParityCard overall={{ sets: overall.sets, systems: [{ system: 'cloud', runs: {} }] }} nameOf={(id) => names[id]} onRefresh={onRefresh} />);
    expect(screen.getByText('No task set has been run yet. Run one from the Evaluations view of a browser.')).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Refresh' }));
    expect(onRefresh).toHaveBeenCalled();
  });
});

describe('the task sets of the desktop of computer use (spec 21.9)', () => {
  it('says that its tasks are done in the folder Practice, not on a practice site', async () => {
    const api = { suite: vi.fn(async () => suiteOf({ system: 'computer' })) } as unknown as SystemsApi;
    render(<SuiteCard system="computer" api={api} />);
    await block('Short tasks');
    expect(screen.getByText(W.systems.suite.leadDesktop)).toBeInTheDocument();
    expect(screen.queryByText(W.systems.suite.lead)).not.toBeInTheDocument();
  });
});
