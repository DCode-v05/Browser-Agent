import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { ChangeResult, Setting, SettingsAnswer, SettingsSource, SettingValue } from '../settings/types';
import { W } from '../wording';
import type { Checklist, Cost, Evals, LogAnswer, Me, Overall, Policy, PolicyChange, SuiteAnswer, SystemInfo, SystemsApi, TaskTrace } from './api';
import { clock, dollars, percent, spanOf } from './format';
import { SettingsList } from './SettingsList';
import { SystemPanel, SystemsPage } from './SystemsPage';

const cloud: SystemInfo = { id: 'cloud', backend: 'remote_headless', state: 'agent', enabled: true, working: false, attention: false, model: 'model-a', log: '/data/logs/cloud.jsonl', records: '/data/evals/cloud' };
const chrome: SystemInfo = { ...cloud, id: 'chrome', backend: 'takeover_chrome', state: 'waiting', log: '/data/logs/chrome.jsonl', records: '/data/evals/chrome' };
const builtIn: SystemInfo = { ...cloud, id: 'builtin', backend: 'bundled_chromium', state: 'ended', log: null, records: '/data/evals/builtin' };

function setting(id: string, title: string, more: Partial<Setting>): Setting {
  return { id, title, description: `What "${title}" does.`, control: 'switch', value: true, default: true, locked: false, applies: 'now', scope: 'system', ...more };
}

/** The settings of one system, as the service answers them, kept here. */
function settingsOf(system: string, refuse?: ChangeResult) {
  const settings: Setting[] = [
    setting('system_enabled', 'Use this browser', {}),
    setting('allow_downloads', 'Let the agent download files', { description: 'Whether the agent may download files.' }),
    setting('page_scripts', 'Let the agent run scripts in pages', { value: false, locked: true }),
    setting('show_agent_pointer', 'Show where the agent is acting', { scope: 'all' }),
    setting('ask_before', 'Ask before', {
      control: 'choice',
      value: 'risky',
      choices: [
        { value: 'never', label: 'Never', disabled: true },
        { value: 'risky', label: 'Risky actions' },
        { value: 'every_action', label: 'Every action' },
      ],
    }),
    setting('picture_quality', 'Picture quality', {
      control: 'choice',
      value: 'standard',
      choices: [
        { value: 'standard', label: 'Standard' },
        { value: 'high', label: 'High' },
      ],
    }),
    setting('blocked_sites', 'Blocked sites', { control: 'list', value: ['ads.example'], fixed: ['internal.example'] }),
    setting('clear_browsing_data', 'Clear browsing data', {
      control: 'action',
      value: null,
      default: null,
      scope: 'all',
      action: 'Clear data',
      confirm: { question: 'Clear cookies and site data?', consequence: 'You will be signed out of sites.', button: 'Clear it' },
    }),
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
  return { source, changed, settings };
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

const COST: Cost = { tasks_counted: 4, input_tokens: 142_300, output_tokens: 3120, usd: 0.41, usd_per_task: 0.1025 };

/** What the admin lets users use, change and see, as the service answers it. */
const POLICY: Policy = {
  systems: [
    { id: 'cloud', allowed: true },
    { id: 'chrome', allowed: true },
    { id: 'builtin', allowed: false },
  ],
  may_change: [
    { id: 'ask_before', title: 'Ask before', description: 'When the agent must stop and wait.', allowed: true },
    { id: 'picture_quality', title: 'Picture quality', description: 'How sharp the live picture is.', allowed: false },
  ],
  sees: [
    { id: 'evaluations', title: 'Evaluations of the browsers they use', description: 'On: a user has the Evaluations view.', allowed: true },
    { id: 'cost', title: 'What the tasks cost', description: 'On: a user also sees what the tasks cost.', allowed: false },
  ],
};

const ME: Me = { role: 'user', systems: ['cloud', 'chrome'], preferred: 'cloud', sees: { evaluations: true, cost: true, traces: true, checklist: true, log: false } };

const EVALS: Evals = {
  system: 'cloud',
  backend: 'remote_headless',
  model: 'model-a',
  models_used: ['model-a'],
  checking: false,
  tasks: { count: 4, answered: 3, failed: 1, stopped: 0, step_limit: 0, ended: 0, success_rate: 0.75, steps: 20, steps_failed: 2, steps_per_task: 5, rated_good: 0, rated_bad: 0 },
  latency: { tool: { count: 20, p50_ms: 84, p95_ms: 620, max_ms: 900 }, model: { count: 24, p50_ms: 1900, p95_ms: 4200, max_ms: 5000 }, by_tool: [{ tool: 'browser_click', count: 9, p50_ms: 70, p95_ms: 300, max_ms: 400, failed: 2 }] },
  time: { task: { count: 4, p50_ms: 14_000, p95_ms: 125_000, max_ms: 125_000 }, model_share: 0.71, tool_share: 0.22, waiting_share: 0.07 },
  cost: COST,
  recent: [TASK],
  checklist: null,
};

const OVERALL: Overall = {
  tasks: { ...EVALS.tasks, count: 6, answered: 5, success_rate: 0.833, steps: 31 },
  latency: EVALS.latency,
  time: EVALS.time,
  cost: { ...COST, usd: 0.5, usd_per_task: 0.0833 },
  systems: [
    { system: 'cloud', tasks: 4, answered: 3, success_rate: 0.75, task_p50_ms: 14_000, input_tokens: 142_300, output_tokens: 3120, usd: 0.41, checks_passed: 10, checks: 11 },
    { system: 'builtin', tasks: 2, answered: 2, success_rate: 1, task_p50_ms: 9000, input_tokens: 9000, output_tokens: 200, usd: null, checks_passed: null, checks: null },
  ],
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

/** The task sets of a browser on which none has been run. */
const suite: SuiteAnswer = {
  system: 'cloud',
  model: 'gpt-test',
  sets: [{ id: 'short', title: 'Short tasks', lead: 'Whether the agent finishes a small task.', tasks: 20, last: null, earlier: [] }],
  running: null,
  trials: 3,
  max_trials: 10,
};

/** A stand-in for the service: it answers as the service would, and remembers what it was asked to change. */
function standIn(over: Partial<SystemsApi> = {}, systems: SystemInfo[] | null = [cloud, chrome, builtIn]) {
  const sources = new Map<string, ReturnType<typeof settingsOf>>();
  const evals = { ...EVALS };
  let policy = POLICY;
  const policyChanges: PolicyChange[] = [];
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
    suite: vi.fn(async () => suite),
    runSuite: vi.fn(async () => ({ ok: true, result: suite }) as const),
    stopSuite: vi.fn(async () => ({ ok: true, result: suite }) as const),
    suiteOverall: vi.fn(async () => null),
    check: vi.fn(async () => {
      evals.checklist = CHECKLIST;
      return { ok: true, result: CHECKLIST } as const;
    }),
    settings: (system) => {
      if (!sources.has(system)) sources.set(system, settingsOf(system));
      return sources.get(system)!.source;
    },
    me: vi.fn(async () => ME),
    prefer: vi.fn(async (system) => ({ ...ME, preferred: system })),
    policy: vi.fn(async () => policy),
    changePolicy: vi.fn(async (changes: PolicyChange) => {
      policyChanges.push(changes);
      // Each line the admin changed, as the service would answer it.
      policy = {
        systems: policy.systems.map((line) => ({ ...line, allowed: changes.systems?.[line.id] ?? line.allowed })),
        may_change: policy.may_change.map((line) => ({ ...line, allowed: changes.may_change?.[line.id] ?? line.allowed })),
        sees: policy.sees.map((line) => ({ ...line, allowed: changes.sees?.[line.id] ?? line.allowed })),
      };
      return policy;
    }),
    overall: vi.fn(async () => OVERALL),
    ...over,
  };
  return { api, policyChanges, changedOn: (system: string) => sources.get(system)?.changed ?? [] };
}

/** The Systems page: what is not one browser's alone. */
function open(over: Partial<SystemsApi> = {}, systems: SystemInfo[] | null = [cloud, chrome, builtIn]) {
  const made = standIn(over, systems);
  const user = userEvent.setup();
  const passwords = { set: vi.fn(async (_role: string, password: string) => (password.length >= 8 ? ({ ok: true } as const) : ({ ok: false, why: 'Use at least 8 characters.' } as const))) };
  const onOpen = vi.fn();
  render(<SystemsPage api={made.api} pollMs={0} wordFor={(system) => system.state} passwords={passwords} onOpen={onOpen} />);
  return { ...made, user, passwords, onOpen };
}

/** The admin, under one browser's own tab. */
function asAdmin(view: 'configuration' | 'evaluations', system = 'cloud', over: Partial<SystemsApi> = {}) {
  const made = standIn(over);
  const user = userEvent.setup();
  const onChanged = vi.fn();
  const onSettings = vi.fn();
  render(<SystemPanel api={made.api} system={system} view={view} role="admin" surface="web" pollMs={0} wordFor={(one) => one.state} onChanged={onChanged} onSettings={onSettings} />);
  return { ...made, user, onChanged, onSettings };
}

const card = (name: string) => screen.findByRole('article', { name });

describe('one browser’s configuration, for the admin (spec 9.17)', () => {
  const A = W.systems.access;

  it('says whose page it is and what it is for, and shows that browser alone', async () => {
    asAdmin('configuration');
    expect(await screen.findByRole('heading', { name: W.systems.panel.title.configuration('Cloud browser') })).toBeInTheDocument();
    expect(screen.getByText(W.systems.panel.lead.configuration)).toBeInTheDocument();
    expect(screen.getAllByRole('article').map((one) => one.getAttribute('aria-label'))).toEqual(['Cloud browser']);
    expect(within(await card('Cloud browser')).getByText('agent')).toBeInTheDocument();
  });

  it('has every setting of the browser on the page, each with what it does and a control that works', async () => {
    const { user, changedOn, onSettings } = asAdmin('configuration');
    const cloudCard = await card('Cloud browser');
    const downloads = await within(cloudCard).findByRole('switch', { name: 'Let the agent download files' });
    expect(downloads).toBeChecked();
    expect(within(cloudCard).getByText('Whether the agent may download files.')).toBeInTheDocument();
    await user.click(downloads);
    await waitFor(() => expect(downloads).not.toBeChecked());
    expect(await within(cloudCard).findByText(W.settings.saved)).toBeInTheDocument();
    // A choice is taken on the page too: there is no screen to open for it.
    await user.click(within(cloudCard).getByRole('radio', { name: /Every action/ }));
    await waitFor(() => expect(within(cloudCard).getByRole('radio', { name: /Every action/ })).toBeChecked());
    expect(changedOn('cloud')).toEqual([{ allow_downloads: false }, { ask_before: 'every_action' }]);
    expect(changedOn('builtin')).toEqual([]);
    // A list of sites is typed here, with the entries config.json holds kept as they are.
    expect(within(cloudCard).getByRole('textbox', { name: 'Blocked sites' })).toHaveValue('ads.example');
    expect(within(cloudCard).getByText('internal.example')).toBeInTheDocument();
    // The window is told what the settings are now: the colour mode is the whole window's.
    expect(onSettings).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    // Every row says what its control does.
    for (const row of cloudCard.querySelectorAll('.setting')) expect(row.querySelector('.setting-description')).not.toBeEmptyDOMElement();
  });

  it('has "Use this browser" once, at the top, and not again among the settings', async () => {
    asAdmin('configuration');
    const cloudCard = await card('Cloud browser');
    await within(cloudCard).findByRole('switch', { name: 'Let the agent download files' });
    expect(within(cloudCard).getAllByRole('switch', { name: /^Use this browser/ })).toHaveLength(1);
    expect(within(cloudCard).getByText(W.systems.useLead)).toBeInTheDocument();
  });

  it('says in words what config.json locks, and draws no control for it', async () => {
    asAdmin('configuration');
    const cloudCard = await card('Cloud browser');
    const row = (await within(cloudCard).findByText('Let the agent run scripts in pages')).closest('.setting') as HTMLElement;
    expect(row).toHaveAttribute('data-locked', 'true');
    expect(within(row).queryByRole('switch')).not.toBeInTheDocument();
    expect(within(row).getByText(W.settings.off)).toBeInTheDocument();
    expect(within(row).getByText(W.systems.locked)).toBeInTheDocument();
  });

  it('says which settings reach users, and which hold for every browser', async () => {
    asAdmin('configuration');
    const cloudCard = await card('Cloud browser');
    const noteOf = (title: string) => within(cloudCard).getByText(title).closest('.setting')?.querySelector('.setting-note')?.textContent ?? null;
    await within(cloudCard).findByText('Ask before');
    // Users may change this one, and are held at the admin's value for that one.
    await waitFor(() => expect(noteOf('Ask before')).toBe(W.systems.usersMay));
    expect(noteOf('Picture quality')).toBe(W.systems.usersHeld);
    expect(noteOf('Show where the agent is acting')).toBe(W.systems.everyBrowser);
    // What is the admin's alone has no line about users.
    expect(noteOf('Let the agent download files')).toBeNull();
    expect(within(cloudCard).getByText(W.systems.forUsersLead)).toBeInTheDocument();
  });

  it('lets users into the browser, or keeps them out, and says what that means', async () => {
    const { user, policyChanges, onChanged } = asAdmin('configuration', 'builtin');
    const builtInCard = await card('Built-in browser');
    const kept = await within(builtInCard).findByRole('switch', { name: `${A.users}: Built-in browser` });
    expect(kept).not.toBeChecked();
    expect(within(builtInCard).getByText(A.usersLead)).toBeInTheDocument();
    await user.click(kept);
    await waitFor(() => expect(kept).toBeChecked());
    expect(policyChanges).toEqual([{ systems: { builtin: true } }]);
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    // Whether a browser runs at all is another switch, and stays as it was.
    expect(within(builtInCard).getByRole('switch', { name: 'Use this browser: Built-in browser' })).toBeChecked();
  });

  it('turns the browser off, and asks the service where the systems stand now', async () => {
    const { api, user, changedOn, onChanged } = asAdmin('configuration', 'builtin');
    await user.click(await within(await card('Built-in browser')).findByRole('switch', { name: 'Use this browser: Built-in browser' }));
    await waitFor(() => expect(changedOn('builtin')).toEqual([{ system_enabled: false }]));
    await waitFor(() => expect(api.list).toHaveBeenCalledTimes(2));
    expect(onChanged).toHaveBeenCalled();
  });

  it('says why a change was refused', async () => {
    const refused = settingsOf('cloud', { ok: false, setting: 'allow_downloads', reason: 'would_loosen' });
    const { user } = asAdmin('configuration', 'cloud', { settings: () => refused.source });
    await user.click(await within(await card('Cloud browser')).findByRole('switch', { name: 'Let the agent download files' }));
    expect(await within(await card('Cloud browser')).findByText(W.settings.refused.would_loosen)).toBeInTheDocument();
  });

  it('restarts and stops a browser that runs, and says what each does', async () => {
    const { api, user } = asAdmin('configuration');
    const cloudCard = await card('Cloud browser');
    expect(within(cloudCard).getByText(W.systems.manageLead.running)).toBeInTheDocument();
    expect(within(cloudCard).getByRole('button', { name: W.systems.stop })).toHaveAttribute('title', W.systems.stopHint);
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.restart }));
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.stop }));
    expect(vi.mocked(api.manage).mock.calls).toEqual([
      ['cloud', 'restart'],
      ['cloud', 'stop'],
    ]);
  });

  it('starts a browser that has stopped', async () => {
    const { api, user } = asAdmin('configuration', 'builtin');
    const builtInCard = await card('Built-in browser');
    expect(within(builtInCard).getByText(W.systems.manageLead.stopped)).toBeInTheDocument();
    await user.click(within(builtInCard).getByRole('button', { name: W.systems.start }));
    expect(vi.mocked(api.manage).mock.calls).toEqual([['builtin', 'start']]);
  });

  it('does not start a person’s own Chrome: it connects by itself', async () => {
    asAdmin('configuration', 'chrome');
    const chromeCard = await card('My Chrome');
    expect(within(chromeCard).queryByRole('button', { name: W.systems.start })).not.toBeInTheDocument();
    expect(within(chromeCard).getByText(W.systems.chromeWaits)).toBeInTheDocument();
  });

  it('says in a sentence what could not be done', async () => {
    const { user } = asAdmin('configuration', 'cloud', { manage: async () => ({ ok: false, why: 'This browser is turned off. Turn it on first.' }) });
    await user.click(within(await card('Cloud browser')).getByRole('button', { name: W.systems.stop }));
    expect(await within(await card('Cloud browser')).findByText('This browser is turned off. Turn it on first.')).toBeInTheDocument();
  });

  it('shows where the browser writes its log, and its newest lines first', async () => {
    const { api, user } = asAdmin('configuration');
    const cloudCard = await card('Cloud browser');
    expect(within(cloudCard).getByText('/data/logs/cloud.jsonl')).toBeInTheDocument();
    expect(within(cloudCard).getByText('/data/evals/cloud')).toBeInTheDocument();
    expect(within(cloudCard).getByText(W.systems.logLead)).toBeInTheDocument();
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.logShow }));
    expect(await within(cloudCard).findByText(W.systems.logNewest(2))).toBeInTheDocument();
    const lines = within(cloudCard).getAllByRole('listitem').filter((line) => line.className === 'system-log-line');
    expect(lines.map((line) => line.getAttribute('data-ok'))).toEqual(['false', 'true']);
    expect(lines[0]).toHaveTextContent(`click${W.systems.didNot}, 80 msCould not click "Pay": it is covered`);
    expect(api.log).toHaveBeenCalledWith('cloud');
    await user.click(within(cloudCard).getByRole('button', { name: W.systems.logHide }));
    expect(within(cloudCard).queryByText(W.systems.logNewest(2))).not.toBeInTheDocument();
  });

  it('says so for a browser whose log is turned off', async () => {
    asAdmin('configuration', 'builtin');
    expect(within(await card('Built-in browser')).getByText(W.systems.logOff)).toBeInTheDocument();
  });

  it('says so when the service does not answer', async () => {
    const made = standIn({}, null);
    render(<SystemPanel api={made.api} system="cloud" view="configuration" role="admin" surface="web" pollMs={0} wordFor={(one) => one.state} />);
    expect(await screen.findByText(W.systems.unreachable)).toBeInTheDocument();
  });
});

describe('the settings on the page follow what changed elsewhere (spec 4.11)', () => {
  const U = W.systems.user;

  function list(version: number, made: ReturnType<typeof settingsOf>) {
    return <SettingsList source={made.source} surface="web" version={version} lockedWords={U.fixed} refused={U.refused} onToast={() => undefined} />;
  }

  it('reads the settings again when the service has been asked again', async () => {
    const made = settingsOf('cloud');
    const { rerender } = render(list(1, made));
    expect(await screen.findByRole('switch', { name: 'Let the agent download files' })).toBeChecked();
    // The admin holds it now: a user is shown the admin's value in words, and no control.
    Object.assign(made.settings.find((one) => one.id === 'allow_downloads')!, { value: false, locked: true });
    rerender(list(2, made));
    await waitFor(() => expect(screen.queryByRole('switch', { name: 'Let the agent download files' })).not.toBeInTheDocument());
    const row = screen.getByText('Let the agent download files').closest('.setting') as HTMLElement;
    expect(within(row).getByText(W.settings.off)).toBeInTheDocument();
    expect(within(row).getByText(U.fixed)).toBeInTheDocument();
  });

  it('does not put back an older answer over a change that is being saved', async () => {
    const made = settingsOf('cloud');
    // The answer to what was asked before the change arrives after the change was saved.
    let late: (answer: SettingsAnswer) => void = () => undefined;
    const before = await made.source.load('web');
    const source: SettingsSource = { ...made.source, load: vi.fn(made.source.load) };
    const user = userEvent.setup();
    const { rerender } = render(<SettingsList source={source} surface="web" version={1} lockedWords={U.fixed} refused={U.refused} onToast={() => undefined} />);
    const downloads = await screen.findByRole('switch', { name: 'Let the agent download files' });
    vi.mocked(source.load).mockImplementationOnce(() => new Promise((answered) => (late = answered)));
    rerender(<SettingsList source={source} surface="web" version={2} lockedWords={U.fixed} refused={U.refused} onToast={() => undefined} />);
    await user.click(downloads);
    await waitFor(() => expect(downloads).not.toBeChecked());
    await act(async () => late(before));
    expect(downloads).not.toBeChecked();
  });

  it('asks before an action that cannot be undone, and says when it is done', async () => {
    const made = settingsOf('cloud');
    const run = vi.fn(async () => undefined);
    const onToast = vi.fn();
    const user = userEvent.setup();
    render(<SettingsList source={{ ...made.source, run }} surface="web" version={1} lockedWords={U.fixed} refused={U.refused} onToast={onToast} />);
    await user.click(await screen.findByRole('button', { name: 'Clear data' }));
    expect(run).not.toHaveBeenCalled();
    await user.click(await screen.findByRole('button', { name: 'Clear it' }));
    await waitFor(() => expect(run).toHaveBeenCalledWith('web', 'clear_browsing_data'));
    expect(onToast).toHaveBeenCalledWith(W.settings.clear.done);
  });
});

describe('what is not one browser’s: the Systems page (spec 4.11)', () => {
  const A = W.systems.access;
  const V = W.systems.overview;

  it('has two views, of what users are allowed and of all systems, and repeats no browser’s settings', async () => {
    open();
    await card(A.title);
    expect(screen.getAllByRole('tab').map((one) => one.textContent)).toEqual([W.systems.view.users, W.systems.view.overview]);
    expect(screen.getByRole('tab', { name: W.systems.view.users })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getAllByRole('article').map((one) => one.getAttribute('aria-label'))).toEqual([A.title]);
    expect(screen.getByText(W.systems.lead)).toBeInTheDocument();
    // What the agent may do in a browser is set under that browser's tab, and nowhere else.
    expect(screen.queryByRole('switch', { name: /Let the agent download files/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('switch', { name: /Use this browser/ })).not.toBeInTheDocument();
  });

  it('says which settings users may change, each with what it is, and changes one line at a time', async () => {
    const { user, policyChanges } = open();
    const users = await card(A.title);
    const ask = await within(users).findByRole('switch', { name: `${A.may_change}: Ask before` });
    const quality = within(users).getByRole('switch', { name: `${A.may_change}: Picture quality` });
    expect(ask).toBeChecked();
    expect(quality).not.toBeChecked();
    expect(within(users).getByText('When the agent must stop and wait.')).toBeInTheDocument();
    expect(within(users).getByText(A.mayChangeLead)).toBeInTheDocument();
    await user.click(ask);
    await waitFor(() => expect(ask).not.toBeChecked());
    await user.click(quality);
    await waitFor(() => expect(quality).toBeChecked());
    expect(policyChanges).toEqual([{ may_change: { ask_before: false } }, { may_change: { picture_quality: true } }]);
  });

  it('says what of the evaluations users may see, each with what it is', async () => {
    const { user, policyChanges } = open();
    const users = await card(A.title);
    const cost = await within(users).findByRole('switch', { name: `${A.sees}: What the tasks cost` });
    expect(cost).not.toBeChecked();
    expect(within(users).getByText('On: a user also sees what the tasks cost.')).toBeInTheDocument();
    expect(within(users).getByRole('switch', { name: `${A.sees}: Evaluations of the browsers they use` })).toBeChecked();
    await user.click(cost);
    await waitFor(() => expect(cost).toBeChecked());
    expect(policyChanges).toEqual([{ sees: { cost: true } }]);
  });

  it('says which browsers users may use, and goes to a browser’s configuration to change it', async () => {
    const { user, onOpen } = open();
    const users = await card(A.title);
    const rows = within(users)
      .getAllByRole('listitem')
      .filter((row) => within(row).queryByRole('button', { name: new RegExp(`^${A.open}`) }));
    expect(rows.map((row) => row.querySelector('.system-row-name')?.textContent)).toEqual([`Cloud browser${A.allowed}`, `My Chrome${A.allowed}`, `Built-in browser${A.kept}`]);
    // It is changed in one place: on that browser's own configuration.
    expect(within(users).queryByRole('switch', { name: /Let users use this browser/ })).not.toBeInTheDocument();
    await user.click(within(users).getByRole('button', { name: `${A.open}: Built-in browser` }));
    expect(onOpen).toHaveBeenCalledWith('builtin', 'configuration');
  });

  it('sets the password users sign in with, and says what the service said of one it did not take', async () => {
    const { user, passwords } = open();
    const users = await card(A.title);
    const box = await within(users).findByLabelText(A.password.user);
    expect(box).toHaveAttribute('type', 'password');
    await user.type(box, 'short');
    await user.click(within(users).getByRole('button', { name: A.set.user }));
    expect(await within(users).findByText('Use at least 8 characters.')).toBeInTheDocument();
    await user.clear(box);
    await user.type(box, 'what users sign in with');
    await user.click(within(users).getByRole('button', { name: A.set.user }));
    expect(await within(users).findByText(A.saved.user)).toBeInTheDocument();
    // The page does not keep what was typed.
    expect(box).toHaveValue('');
    expect(passwords.set.mock.calls).toEqual([
      ['user', 'short'],
      ['user', 'what users sign in with'],
    ]);
    await user.type(within(users).getByLabelText(A.password.admin), 'the admin’s own words');
    await user.click(within(users).getByRole('button', { name: A.set.admin }));
    expect(await within(users).findByText(A.saved.admin)).toBeInTheDocument();
    expect(passwords.set.mock.calls[2]).toEqual(['admin', 'the admin’s own words']);
  });

  it('shows where each browser stands, and goes to its own configuration and evaluations', async () => {
    const { user, onOpen } = open();
    await user.click(await screen.findByRole('tab', { name: W.systems.view.overview }));
    const browsers = await card(V.title);
    expect(screen.getAllByRole('article').map((one) => one.getAttribute('aria-label'))).toEqual([V.title, W.systems.overall.title, W.systems.suite.parity.title]);
    const rows = within(within(browsers).getByRole('table')).getAllByRole('row').slice(1);
    expect(rows.map((row) => [within(row).getByRole('rowheader').textContent, ...within(row).getAllByRole('cell').slice(0, 4).map((cell) => cell.textContent)])).toEqual([
      ['Cloud browser', 'agent', V.on, V.usersYes, 'model-a'],
      ['My Chrome', 'waiting', V.on, V.usersYes, 'model-a'],
      ['Built-in browser', 'ended', V.on, V.usersNo, 'model-a'],
    ]);
    // Nothing is changed here: each browser is set up under its own tab.
    expect(within(browsers).queryByRole('switch')).not.toBeInTheDocument();
    await user.click(within(browsers).getByRole('button', { name: V.evaluations('Cloud browser') }));
    await user.click(within(browsers).getByRole('button', { name: V.configuration('Built-in browser') }));
    expect(onOpen.mock.calls).toEqual([
      ['cloud', 'evaluations'],
      ['builtin', 'configuration'],
    ]);
  });

  it('shows the tasks of every system as one, with a line for each system', async () => {
    const { user } = open();
    await user.click(await screen.findByRole('tab', { name: W.systems.view.overview }));
    const all = await card(W.systems.overall.title);
    expect(await within(all).findByText(W.systems.evals.tasksLine(6, 31))).toBeInTheDocument();
    expect(within(all).getByText('83% answered (5 of 6)')).toBeInTheDocument();
    expect(within(all).getByText('$0.5000 in all, $0.0833 a task')).toBeInTheDocument();
    const rows = within(within(all).getByRole('table')).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent))).toEqual([
      ['4', '75%', '14.0 s', '145,420', '$0.4100', '10 of 11 passed'],
      // A system with no price set and no checklist run says so, and makes nothing up.
      ['2', '100%', '9.0 s', '9,200', '–', W.systems.overall.notRun],
    ]);
    expect(rows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual(['Cloud browser', 'Built-in browser']);
  });

  it('says so when the service does not answer', async () => {
    open({}, null);
    expect(await screen.findByText(W.systems.unreachable)).toBeInTheDocument();
  });
});

describe('a user, under a browser’s own tab (spec 4.11)', () => {
  const U = W.systems.user;

  function asUser(view: 'settings' | 'evaluations', over: Partial<SystemsApi> = {}, me: Me = ME) {
    const made = standIn(over, [cloud, chrome]);
    const onPrefer = vi.fn();
    const user = userEvent.setup();
    const panel = (mine: Me) => <SystemPanel api={made.api} system="cloud" view={view} role="user" me={mine} onPrefer={onPrefer} surface="web" pollMs={0} wordFor={(system) => system.state} />;
    const { rerender } = render(panel(me));
    return { ...made, user, onPrefer, as: (mine: Me) => rerender(panel(mine)) };
  }

  it('says whose page it is and what it is for', async () => {
    asUser('settings');
    expect(await screen.findByRole('heading', { name: W.systems.panel.title.settings('Cloud browser') })).toBeInTheDocument();
    expect(screen.getByText(W.systems.panel.lead.settings)).toBeInTheDocument();
  });

  it('chooses the browser their window opens on, among those they may use', async () => {
    const { user, onPrefer } = asUser('settings');
    const cloudCard = await card('Cloud browser');
    const preferred = within(cloudCard).getByRole('combobox', { name: new RegExp(`^${U.preferred}`) });
    expect(preferred).toHaveValue('cloud');
    expect(within(preferred).getAllByRole('option').map((option) => option.textContent)).toEqual(['Cloud browser', 'My Chrome']);
    expect(within(cloudCard).getByText(U.preferredLead)).toBeInTheDocument();
    expect(within(cloudCard).getByText(U.isPreferred)).toBeInTheDocument();
    await user.selectOptions(preferred, 'chrome');
    expect(onPrefer).toHaveBeenCalledWith('chrome');
  });

  it('has a working control for every setting that is theirs, each with what it does', async () => {
    const { user, changedOn } = asUser('settings');
    const cloudCard = await card('Cloud browser');
    const downloads = await within(cloudCard).findByRole('switch', { name: 'Let the agent download files' });
    await user.click(downloads);
    await waitFor(() => expect(downloads).not.toBeChecked());
    await user.click(within(cloudCard).getByRole('radio', { name: /Every action/ }));
    await waitFor(() => expect(within(cloudCard).getByRole('radio', { name: /Every action/ })).toBeChecked());
    expect(changedOn('cloud')).toEqual([{ allow_downloads: false }, { ask_before: 'every_action' }]);
    // A choice looser than the admin has it is shown, and is not theirs to take.
    const never = within(cloudCard).getByRole('radio', { name: /Never/ });
    expect(never).toBeDisabled();
    expect(never.closest('label')).toHaveTextContent(U.fixed);
    for (const one of within(cloudCard).getAllByRole('switch')) expect(one).toBeEnabled();
    // A setting that is not this browser's alone says so.
    expect(within(cloudCard).getByText('Show where the agent is acting').closest('.setting')).toHaveTextContent(U.everyBrowser);
    for (const row of cloudCard.querySelectorAll('.setting')) expect(row.querySelector('.setting-description')).not.toBeEmptyDOMElement();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('is told in words what the admin holds, and has no control for it', async () => {
    asUser('settings');
    const cloudCard = await card('Cloud browser');
    const row = (await within(cloudCard).findByText('Let the agent run scripts in pages')).closest('.setting') as HTMLElement;
    expect(within(row).queryByRole('switch')).not.toBeInTheDocument();
    expect(within(row).getByText(W.settings.off)).toBeInTheDocument();
    expect(within(row).getByText(U.fixed)).toBeInTheDocument();
  });

  it('has nothing to manage the browser with: that is the admin’s', async () => {
    asUser('settings');
    const cloudCard = await card('Cloud browser');
    await within(cloudCard).findByRole('switch', { name: 'Let the agent download files' });
    for (const admins of [W.systems.stop, W.systems.restart, W.systems.start]) expect(within(cloudCard).queryByRole('button', { name: admins })).not.toBeInTheDocument();
    expect(within(cloudCard).queryByRole('switch', { name: /Let users use this browser/ })).not.toBeInTheDocument();
    expect(within(cloudCard).queryByText('/data/logs/cloud.jsonl')).not.toBeInTheDocument();
  });

  it('says why a change was not taken, in words about the admin', async () => {
    const refused = settingsOf('cloud', { ok: false, setting: 'allow_downloads', reason: 'would_loosen' });
    const { user } = asUser('settings', { settings: () => refused.source });
    await user.click(await within(await card('Cloud browser')).findByRole('switch', { name: 'Let the agent download files' }));
    expect(await within(await card('Cloud browser')).findByText(U.refused.would_loosen)).toBeInTheDocument();
  });

  it('is shown of the evaluations what the admin lets users see', async () => {
    const kept: Evals = { ...EVALS, cost: null, recent: [], checklist: null, may: { cost: false, traces: false, checklist: false } };
    asUser('evaluations', { evals: async () => kept });
    const cloudCard = await card('Cloud browser');
    const E = W.systems.evals;
    expect(screen.getByText(W.systems.panel.lead.evaluations.user)).toBeInTheDocument();
    // How the tasks went is there. What they cost, the checklist and the tasks themselves are not.
    expect(await within(cloudCard).findByText(E.tasksLine(4, 20))).toBeInTheDocument();
    expect(within(cloudCard).getByText(E.latency)).toBeInTheDocument();
    expect(within(cloudCard).queryByText(E.cost)).not.toBeInTheDocument();
    expect(within(cloudCard).queryByRole('button', { name: E.run })).not.toBeInTheDocument();
    expect(within(cloudCard).queryByText(E.traces)).not.toBeInTheDocument();
  });

  it('is shown all of it where the admin keeps nothing back', async () => {
    const shown: Evals = { ...EVALS, may: { cost: true, traces: true, checklist: true } };
    asUser('evaluations', { evals: async () => shown });
    const cloudCard = await card('Cloud browser');
    const E = W.systems.evals;
    expect(await within(cloudCard).findByText(E.cost)).toBeInTheDocument();
    expect(within(cloudCard).getByRole('button', { name: E.run })).toBeInTheDocument();
    expect(within(cloudCard).getByText('Find the cheapest fare')).toBeInTheDocument();
  });

  it('asks for the evaluations again when what the admin lets users see changes', async () => {
    const { api, as } = asUser('evaluations');
    await within(await card('Cloud browser')).findByText(W.systems.evals.tasksLine(4, 20));
    expect(api.evals).toHaveBeenCalledTimes(1);
    // The same as before: nothing is asked.
    as({ ...ME });
    as({ ...ME, sees: { ...ME.sees, cost: false } });
    await waitFor(() => expect(api.evals).toHaveBeenCalledTimes(2));
  });
});

describe('one browser’s evaluations (spec 12.6)', () => {
  const E = W.systems.evals;

  async function evaluations(over: Partial<SystemsApi> = {}) {
    const opened = asAdmin('evaluations', 'cloud', over);
    const cloudCard = await card('Cloud browser');
    await within(cloudCard).findByText(E.tasksLine(4, 20));
    return { ...opened, cloudCard };
  }

  it('says whose page it is, and what each line of it is', async () => {
    const { cloudCard } = await evaluations();
    expect(screen.getByRole('heading', { name: W.systems.panel.title.evaluations('Cloud browser') })).toBeInTheDocument();
    expect(screen.getByText(W.systems.panel.lead.evaluations.admin)).toBeInTheDocument();
    for (const hint of Object.values(E.hint)) expect(within(cloudCard).getByText(hint)).toBeInTheDocument();
    for (const lead of [E.performanceLead, E.checklistLead, E.tracesLead]) expect(within(cloudCard).getByText(lead)).toBeInTheDocument();
    expect(within(cloudCard).getByRole('button', { name: E.good })).toHaveAttribute('title', E.goodHint);
    expect(within(cloudCard).getByRole('button', { name: W.systems.refresh })).toHaveAttribute('title', W.systems.refreshHint);
  });

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
    const unpriced = { ...EVALS, cost: { ...COST, usd: null, usd_per_task: null } };
    const { cloudCard } = await evaluations({ evals: async () => unpriced });
    expect(within(cloudCard).getByText(E.noPrice)).toBeInTheDocument();
  });

  it('says so for a browser that has done no task', async () => {
    const none = { ...EVALS, tasks: { ...EVALS.tasks, count: 0, success_rate: null }, recent: [], latency: { ...EVALS.latency, by_tool: [] } };
    asAdmin('evaluations', 'cloud', { evals: async () => none });
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
