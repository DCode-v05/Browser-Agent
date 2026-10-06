import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { ChangeResult, Setting, SettingsAnswer, SettingsSource, SettingValue } from '../settings/types';
import { W } from '../wording';
import type { Checklist, Evals, LogAnswer, SystemInfo, SystemsApi, TaskTrace } from './api';
import { clock, dollars, percent, spanOf } from './format';
import { SystemsPage } from './SystemsPage';

const cloud: SystemInfo = { id: 'cloud', backend: 'remote_headless', state: 'agent', enabled: true, working: false, attention: false, model: 'model-a', log: '/data/logs/cloud.jsonl', records: '/data/evals/cloud' };
const chrome: SystemInfo = { ...cloud, id: 'chrome', backend: 'takeover_chrome', state: 'waiting', log: '/data/logs/chrome.jsonl', records: '/data/evals/chrome' };
const builtIn: SystemInfo = { ...cloud, id: 'builtin', backend: 'bundled_chromium', state: 'ended', log: null, records: '/data/evals/builtin' };

function setting(id: string, title: string, more: Partial<Setting>): Setting {
  return { id, title, description: '', control: 'switch', value: true, default: true, locked: false, applies: 'now', scope: 'system', ...more };
}

/** The settings of one system, as the service answers them, kept here. */
function settingsOf(system: string, refuse?: ChangeResult) {
  const settings: Setting[] = [
    setting('system_enabled', 'Use this browser', {}),
    setting('allow_downloads', 'Let the agent download files', {}),
    setting('page_scripts', 'Let the agent run scripts in pages', { value: false, locked: true }),
    setting('show_agent_pointer', 'Show where the agent is acting', { scope: 'all' }),
    setting('ask_before', 'Ask before', { control: 'choice', value: 'risky', choices: [{ value: 'risky', label: 'Risky actions' }] }),
    setting('blocked_sites', 'Blocked sites', { control: 'list', value: ['ads.example'], fixed: ['internal.example'] }),
  ];
  const answer = (): SettingsAnswer => ({ surface: 'web', system, groups: [{ id: 'all', title: 'All', settings: settings.map((one) => ({ ...one })) }] });
  const changed: Record<string, SettingValue>[] = [];
  const source: SettingsSource = {
    load: async () => answer(),
    change: async (_surface, changes) => {
      changed.push(changes);
      if (refuse) return refuse;
      for (const [id, value] of Object.entries(changes)) settings.find((one) => one.id === id)!.value = value;
      return { ok: true, answer: answer() };
    },
    run: async () => undefined,
    config: async () => ({ version: '0.1.0', browser: 'Chromium', changed: [] }),
  };
  return { source, changed };
}

const CHECKLIST: Checklist = {
  ran: 1_791_280_000,
  duration_ms: 420,
  passed: 2,
  failed: 1,
  skipped: 1,
  checks: [
    { id: 'answers', title: 'The browser answers', state: 'ok', detail: '', ms: 12 },
    { id: 'opens', title: 'Opens a page', state: 'ok', detail: '', ms: 80 },
    { id: 'types', title: 'Types into a field', state: 'failed', detail: 'the form has no field to type into', ms: null },
    { id: 'person', title: 'A person can be asked', state: 'skipped', detail: 'no one is watching this browser', ms: null },
  ],
};

const TASK = { id: 't1', started: 1_791_280_000, task: 'Find the cheapest fare', answer: '61 euros', outcome: 'answered' as const, model: 'model-a', duration_ms: 14_200, steps: 6, steps_failed: 1, model_calls: 7, model_ms: 9000, tool_ms: 4000, waited_ms: 1200, input_tokens: 12_000, output_tokens: 300, tokens_known: true, cost_usd: 0.027, rating: null };

const EVALS: Evals = {
  system: 'cloud',
  backend: 'remote_headless',
  model: 'model-a',
  models_used: ['model-a'],
  checking: false,
  tasks: { count: 4, answered: 3, failed: 1, stopped: 0, step_limit: 0, ended: 0, success_rate: 0.75, steps: 20, steps_failed: 2, steps_per_task: 5, rated_good: 0, rated_bad: 0 },
  latency: { tool: { count: 20, p50_ms: 84, p95_ms: 620, max_ms: 900 }, model: { count: 24, p50_ms: 1900, p95_ms: 4200, max_ms: 5000 }, by_tool: [{ tool: 'browser_click', count: 9, p50_ms: 70, p95_ms: 300, max_ms: 400, failed: 2 }] },
  time: { task: { count: 4, p50_ms: 14_000, p95_ms: 125_000, max_ms: 125_000 }, model_share: 0.71, tool_share: 0.22, waiting_share: 0.07 },
  cost: { tasks_counted: 4, input_tokens: 142_300, output_tokens: 3120, usd: 0.41, usd_per_task: 0.1025 },
  recent: [TASK],
  checklist: null,
};

const TRACE: TaskTrace = {
  ...TASK,
  spans: [
    { kind: 'model', name: 'model-a', at_ms: 0, ms: 1900, ok: true, waited_ms: 0, input_tokens: 1200, output_tokens: 40 },
    { kind: 'tool', name: 'browser_upload_file', at_ms: 1900, ms: 3000, ok: false, waited_ms: 1200, input_tokens: 0, output_tokens: 0 },
  ],
};

const LOG: LogAnswer = {
  path: '/data/logs/cloud.jsonl',
  size: 200,
  lines: [
    { ts: 1_791_280_000, tool: 'browser_navigate', ok: true, ms: 640, chars: 300, result: 'Navigated to https://example.com/' },
    { ts: 1_791_280_005, tool: 'browser_click', ok: false, ms: 80, chars: 90, result: 'Could not click "Pay": it is covered' },
  ],
};

function open(over: Partial<SystemsApi> = {}, systems: SystemInfo[] | null = [cloud, chrome, builtIn]) {
  const sources = new Map<string, ReturnType<typeof settingsOf>>();
  const evals = { ...EVALS };
  const api: SystemsApi = {
    list: vi.fn(async () => systems),
    manage: vi.fn(async () => ({ ok: true }) as const),
    log: vi.fn(async () => LOG),
    evals: vi.fn(async () => ({ ...evals, recent: evals.recent.map((task) => ({ ...task })) })),
    trace: vi.fn(async () => TRACE),
    rate: vi.fn(async (_system, _task, rating) => {
      evals.recent = [{ ...TASK, rating }];
      evals.tasks = { ...evals.tasks, rated_good: rating === 'good' ? 1 : 0 };
      return true;
    }),
    check: vi.fn(async () => {
      evals.checklist = CHECKLIST;
      return { ok: true, result: CHECKLIST } as const;
    }),
    settings: (system) => {
      if (!sources.has(system)) sources.set(system, settingsOf(system));
      return sources.get(system)!.source;
    },
    ...over,
  };
  const user = userEvent.setup();
  render(<SystemsPage api={api} surface="web" pollMs={0} wordFor={(system) => system.state} />);
  return { api, user, changedOn: (system: string) => sources.get(system)?.changed ?? [] };
}

const card = (name: string) => screen.findByRole('article', { name });

describe('the systems, to set up and to manage (spec 9.17)', () => {
  it('has a card for each browser, with where it stands', async () => {
    open();
    expect((await screen.findAllByRole('article')).map((one) => one.getAttribute('aria-label'))).toEqual(['Cloud browser', 'My Chrome', 'Built-in browser']);
    expect(screen.getByRole('tab', { name: W.systems.configuration })).toHaveAttribute('aria-selected', 'true');
    expect(within(await card('Cloud browser')).getByText('agent')).toBeInTheDocument();
  });

  it('shows what the agent may do in a browser, and changes it for that browser alone', async () => {
    const { user, changedOn } = open();
    const cloudCard = await card('Cloud browser');
    const downloads = await within(cloudCard).findByRole('switch', { name: 'Let the agent download files: Cloud browser' });
    expect(downloads).toBeChecked();
    await user.click(downloads);
    await waitFor(() => expect(downloads).not.toBeChecked());
    expect(changedOn('cloud')).toEqual([{ allow_downloads: false }]);
    expect(changedOn('builtin')).toEqual([]);
    // What is every browser's is not listed as this browser's own.
    expect(within(cloudCard).queryByRole('switch', { name: /Show where the agent is acting/ })).not.toBeInTheDocument();
    // What the deployment requires is shown, and is not the person's to change.
    expect(within(cloudCard).getByRole('switch', { name: 'Let the agent run scripts in pages: Cloud browser' })).toBeDisabled();
    expect(within(cloudCard).getByText(W.systems.locked)).toBeInTheDocument();
    // What is not a switch is said in the words of its choices.
    expect(within(cloudCard).getByText('Risky actions')).toBeInTheDocument();
    expect(within(cloudCard).getByText('2 sites')).toBeInTheDocument();
  });

  it('turns a browser off, and asks the service where the systems stand now', async () => {
    const { api, user, changedOn } = open();
    await user.click(await within(await card('Built-in browser')).findByRole('switch', { name: 'Use this browser: Built-in browser' }));
    await waitFor(() => expect(changedOn('builtin')).toEqual([{ system_enabled: false }]));
    await waitFor(() => expect(api.list).toHaveBeenCalledTimes(2));
  });

  it('says why a change was refused', async () => {
    const refused = settingsOf('cloud', { ok: false, setting: 'allow_downloads', reason: 'would_loosen' });
    open({ settings: () => refused.source });
    const user = userEvent.setup();
    await user.click(await within(await card('Cloud browser')).findByRole('switch', { name: 'Let the agent download files: Cloud browser' }));
    expect(await within(await card('Cloud browser')).findByText(W.settings.refused.would_loosen)).toBeInTheDocument();
  });

  it('restarts and stops a browser that runs, and starts one that does not', async () => {
    const { api, user } = open();
    const cloudCard = await card('Cloud browser');
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.restart }));
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.stop }));
    await user.click(within(await card('Built-in browser')).getByRole('button', { name: W.systems.start }));
    expect(vi.mocked(api.manage).mock.calls).toEqual([
      ['cloud', 'restart'],
      ['cloud', 'stop'],
      ['builtin', 'start'],
    ]);
    // A person's own Chrome is not started from here: it connects by itself.
    const chromeCard = await card('My Chrome');
    expect(within(chromeCard).queryByRole('button', { name: W.systems.start })).not.toBeInTheDocument();
    expect(within(chromeCard).getByText(W.systems.chromeWaits)).toBeInTheDocument();
  });

  it('says in a sentence what could not be done', async () => {
    const { user } = open({ manage: async () => ({ ok: false, why: 'This browser is turned off. Turn it on first.' }) });
    await user.click(within(await card('Cloud browser')).getByRole('button', { name: W.systems.stop }));
    expect(await within(await card('Cloud browser')).findByText('This browser is turned off. Turn it on first.')).toBeInTheDocument();
  });

  it('shows where a browser writes its log, and its newest lines first', async () => {
    const { api, user } = open();
    const cloudCard = await card('Cloud browser');
    expect(within(cloudCard).getByText('/data/logs/cloud.jsonl')).toBeInTheDocument();
    expect(within(cloudCard).getByText('/data/evals/cloud')).toBeInTheDocument();
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.logShow }));
    expect(await within(cloudCard).findByText(W.systems.logNewest(2))).toBeInTheDocument();
    const lines = within(cloudCard).getAllByRole('listitem').filter((line) => line.className === 'system-log-line');
    expect(lines.map((line) => line.getAttribute('data-ok'))).toEqual(['false', 'true']);
    expect(lines[0]).toHaveTextContent(`click${W.systems.didNot}, 80 msCould not click "Pay": it is covered`);
    expect(api.log).toHaveBeenCalledWith('cloud');
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.logHide }));
    expect(within(cloudCard).queryByText(W.systems.logNewest(2))).not.toBeInTheDocument();
    // A browser whose log a person turned off says so.
    expect(within(await card('Built-in browser')).getByText(W.systems.logOff)).toBeInTheDocument();
  });

  it('opens the whole settings screen of one browser', async () => {
    const { user } = open();
    await user.click(within(await card('My Chrome')).getByRole('button', { name: W.systems.allSettings }));
    const dialog = await screen.findByRole('dialog', { name: W.settings.title });
    expect(await within(dialog).findByText('Blocked sites')).toBeInTheDocument();
  });

  it('says so when the service does not answer', async () => {
    open({}, null);
    expect(await screen.findByText(W.systems.unreachable)).toBeInTheDocument();
  });
});

describe('the systems, evaluated (spec 12.6)', () => {
  const E = W.systems.evals;

  async function evaluations(over: Partial<SystemsApi> = {}) {
    const opened = open(over);
    await opened.user.click(await screen.findByRole('tab', { name: W.systems.evaluations }));
    const cloudCard = await card('Cloud browser');
    await within(cloudCard).findByText(E.tasksLine(4, 20));
    return { ...opened, cloudCard };
  }

  it('says the model, how the tasks ended, the latency, where the time went and the cost', async () => {
    const { cloudCard } = await evaluations();
    const said = within(cloudCard);
    expect(said.getByText('model-a')).toBeInTheDocument();
    expect(said.getByText('75% answered (3 of 4)')).toBeInTheDocument();
    expect(said.getByText('1 failed, 0 stopped by you, 0 ran out of steps')).toBeInTheDocument();
    expect(said.getByText('2 of 20 steps failed')).toBeInTheDocument();
    expect(said.getByText('A step in the browser: 84 ms typical, 620 ms slow')).toBeInTheDocument();
    expect(said.getByText('A reply of the model: 1.9 s typical, 4.2 s slow')).toBeInTheDocument();
    expect(said.getByText('A task: 14.0 s typical, 2 min 5 s slow')).toBeInTheDocument();
    expect(said.getByText('71% the model, 22% the browser, 7% waiting for you')).toBeInTheDocument();
    expect(said.getByText('142,300 tokens in, 3,120 out')).toBeInTheDocument();
    expect(said.getByText('$0.4100 in all, $0.1025 a task')).toBeInTheDocument();
    // Performance by tool: how often, how long, how often it failed.
    const row = within(said.getByRole('table')).getByRole('row', { name: /click/ });
    expect(within(row).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['9', '70 ms', '300 ms', '2']);
  });

  it('makes up no cost where no price is set, and none where the model did not say its tokens', async () => {
    const unpriced = { ...EVALS, cost: { ...EVALS.cost, usd: null, usd_per_task: null } };
    const { cloudCard } = await evaluations({ evals: async () => unpriced });
    expect(within(cloudCard).getByText(E.noPrice)).toBeInTheDocument();
  });

  it('says so for a browser that has done no task', async () => {
    const none = { ...EVALS, tasks: { ...EVALS.tasks, count: 0, success_rate: null }, recent: [], latency: { ...EVALS.latency, by_tool: [] } };
    open({ evals: async () => none });
    const user = userEvent.setup();
    await user.click(await screen.findByRole('tab', { name: W.systems.evaluations }));
    const cloudCard = await card('Cloud browser');
    expect(await within(cloudCard).findByText(E.none)).toBeInTheDocument();
    expect(within(cloudCard).queryByText(E.quality)).not.toBeInTheDocument();
    expect(within(cloudCard).getByText(E.neverRun)).toBeInTheDocument();
  });

  it('runs the checklist and shows each line of it', async () => {
    const { api, user, cloudCard } = await evaluations();
    await user.click(within(cloudCard).getByRole('button', { name: E.run }));
    expect(await within(cloudCard).findByText(new RegExp(`^${E.passed(2, 4)}`))).toBeInTheDocument();
    expect(api.check).toHaveBeenCalledWith('cloud');
    const lines = within(cloudCard).getAllByRole('listitem').filter((line) => line.className === 'system-check');
    expect(lines.map((line) => line.getAttribute('data-state'))).toEqual(['ok', 'ok', 'failed', 'skipped']);
    expect(lines[0]).toHaveTextContent('Passed: The browser answers12 ms');
    // What failed says why, and what was passed over says why too.
    expect(lines[2]).toHaveTextContent('Failed: Types into a fieldthe form has no field to type into');
    expect(lines[3]).toHaveTextContent('Skipped: A person can be askedno one is watching this browser');
  });

  it('says why the checklist could not be run', async () => {
    const busy = 'This browser is busy. Run the checklist when its task is finished.';
    const { user, cloudCard } = await evaluations({ check: async () => ({ ok: false, why: busy }) });
    await user.click(within(cloudCard).getByRole('button', { name: E.run }));
    expect(await within(cloudCard).findByText(busy)).toBeInTheDocument();
  });

  it('lists the recent tasks, takes a person’s word on an answer, and takes it back', async () => {
    const { api, user, cloudCard } = await evaluations();
    expect(within(cloudCard).getByText('Find the cheapest fare')).toBeInTheDocument();
    expect(within(cloudCard).getByText(`${E.outcome.answered}. ${E.facts('14.2 s', 6, 7)}, $0.0270`)).toBeInTheDocument();
    await user.click(within(cloudCard).getByRole('button', { name: E.good }));
    expect(await within(cloudCard).findByText(E.rated(1, 0))).toBeInTheDocument();
    await user.click(within(cloudCard).getByRole('button', { name: E.good }));
    expect(vi.mocked(api.rate).mock.calls).toEqual([
      ['cloud', 't1', 'good'],
      ['cloud', 't1', null],
    ]);
  });

  it('shows the trace of a task: each reply and each step, where and how long it was', async () => {
    const { api, user, cloudCard } = await evaluations();
    await user.click(within(cloudCard).getByRole('button', { name: E.showTrace }));
    const trace = await within(cloudCard).findByRole('list', { name: E.trace });
    const spans = within(trace).getAllByRole('listitem');
    expect(spans.map((span) => [span.getAttribute('data-kind'), span.getAttribute('data-ok')])).toEqual([
      ['model', 'true'],
      ['tool', 'false'],
    ]);
    expect(spans[0]).toHaveTextContent(`${E.theModel}1.9 s${E.spanTokens('1,200', '40')}`);
    // A step that waited for a person says how much of its time was that wait.
    expect(spans[1]).toHaveTextContent(`upload_file3.0 s${E.waited('1.2 s')}`);
    expect(api.trace).toHaveBeenCalledWith('cloud', 't1');
    await user.click(within(cloudCard).getByRole('button', { name: E.hideTrace }));
    expect(within(cloudCard).queryByRole('list', { name: E.trace })).not.toBeInTheDocument();
  });
});

describe('how the Systems page writes a time, a share and an amount', () => {
  it.each([
    [null, '–'],
    [0, '0 ms'],
    [84.4, '84 ms'],
    [999.4, '999 ms'],
    [1900, '1.9 s'],
    [59_940, '59.9 s'],
    [125_000, '2 min 5 s'],
  ])('%s is %s', (ms, said) => {
    expect(spanOf(ms)).toBe(said);
  });

  it('writes a share as a percentage and money with the digits that say anything', () => {
    expect([percent(0.714), percent(1), percent(null)]).toEqual(['71%', '100%', '–']);
    expect([dollars(0.027), dollars(0.41), dollars(12.5)]).toEqual(['$0.0270', '$0.4100', '$12.50']);
    expect(clock(1_791_280_000)).toMatch(/\d{1,2}:\d{2}:\d{2}/);
  });
});
