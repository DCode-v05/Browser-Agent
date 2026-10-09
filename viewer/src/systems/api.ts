// The browsers of the window as systems (spec 9.17): what the service says of each, and what a
// person may ask it to do with one. The token goes in a header, never in the address.

import type { Role } from '../auth/api';
import type { Backend } from '../protocol';
import { settingsFrom } from '../settings/api';
import type { SettingsSource } from '../settings/types';

export interface SystemInfo {
  id: string;
  backend: Backend;
  /** Who is driving, as the session says it; or, with no session, `starting`, `waiting`, `failed` or `off`. */
  state: string;
  enabled: boolean;
  working: boolean;
  attention: boolean;
  /** The model that plans the agent's steps on this browser. */
  model: string;
  /** Where this browser's log is written. Null when it is turned off. Not told to a user the admin keeps the log from. */
  log?: string | null;
  /** The folder that holds the record of this browser's tasks. The admin's to know. */
  records?: string;
  note?: string;
}

/** What of a system's evaluations a person may be shown (spec 12.6). The admin says so for users. */
export type Seen = 'evaluations' | 'cost' | 'traces' | 'checklist' | 'log';

/** Who is signed in, and what they may use and see (spec 4.11). */
export interface Me {
  role: Role;
  /** The browsers this person may use. */
  systems: string[];
  /** The browser their window opens on. Null where they may use none. */
  preferred: string | null;
  sees: Record<Seen, boolean>;
}

export interface PolicyLine {
  id: string;
  title?: string;
  /** What the line lets a user do, for the admin who decides it. */
  description?: string;
  allowed: boolean;
}

/** What the admin lets users use, change and see. */
export interface Policy {
  systems: PolicyLine[];
  may_change: PolicyLine[];
  sees: PolicyLine[];
}

export type PolicyChange = Partial<Record<keyof Policy, Record<string, boolean>>>;

export interface Times {
  count: number;
  p50_ms: number | null;
  p95_ms: number | null;
  max_ms: number | null;
}

export type Outcome = 'answered' | 'failed' | 'stopped' | 'step_limit' | 'ended';
export type Rating = 'good' | 'bad';

export interface TaskRow {
  id: string;
  /** When it began, in seconds since 1970. */
  started: number;
  task: string;
  answer: string;
  outcome: Outcome;
  model: string;
  duration_ms: number;
  steps: number;
  steps_failed: number;
  model_calls: number;
  model_ms: number;
  tool_ms: number;
  waited_ms: number;
  input_tokens: number;
  output_tokens: number;
  tokens_known: boolean;
  cost_usd: number | null;
  rating: Rating | null;
}

export interface Span {
  kind: 'model' | 'tool';
  name: string;
  /** When it began, counted from the start of the task. */
  at_ms: number;
  ms: number;
  ok: boolean;
  waited_ms: number;
  input_tokens: number;
  output_tokens: number;
}

export interface TaskTrace extends TaskRow {
  spans: Span[];
}

export interface Check {
  id: string;
  title: string;
  state: 'ok' | 'failed' | 'skipped';
  detail: string;
  ms: number | null;
}

export interface Checklist {
  ran: number;
  duration_ms: number;
  passed: number;
  failed: number;
  skipped: number;
  checks: Check[];
}

export interface Evals {
  system: string;
  backend: Backend;
  model: string;
  models_used: string[];
  /** The checklist is running on this browser now. */
  checking: boolean;
  tasks: {
    count: number;
    answered: number;
    failed: number;
    stopped: number;
    step_limit: number;
    ended: number;
    success_rate: number | null;
    steps: number;
    steps_failed: number;
    steps_per_task: number | null;
    rated_good: number;
    rated_bad: number;
  };
  latency: { tool: Times; model: Times; by_tool: (Times & { tool: string; failed: number })[] };
  time: { task: Times; model_share: number | null; tool_share: number | null; waiting_share: number | null };
  /** Null for a user the admin keeps the cost from. */
  cost: Cost | null;
  recent: TaskRow[];
  checklist: Checklist | null;
  /** What this person may be shown. Without it, everything. */
  may?: { cost: boolean; traces: boolean; checklist: boolean };
}

export interface Cost {
  tasks_counted: number;
  input_tokens: number;
  output_tokens: number;
  usd: number | null;
  usd_per_task: number | null;
}

/** One system in the admin's view of the whole. */
export interface OverallLine {
  system: string;
  tasks: number;
  answered: number;
  success_rate: number | null;
  task_p50_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  usd: number | null;
  checks_passed: number | null;
  checks: number | null;
}

/** The tasks of every system as one (spec 12.6). */
export interface Overall {
  tasks: Evals['tasks'];
  latency: Evals['latency'];
  time: Evals['time'];
  cost: Cost;
  systems: OverallLine[];
}

/** The task sets of a system (spec 12.7). */
export type SetName = 'short' | 'confirm' | 'attack' | 'long' | 'infeasible';
/** Who does the tasks: the agent with its model, or the reference solutions, which need no model. */
export type SuiteMode = 'agent' | 'reference';

export interface SuiteTrial {
  passed: boolean;
  /** Why it did not pass, in a few words. */
  why: string;
  /** How many times a person would have been asked. */
  asked: number;
  /** For a planted instruction: whether it was followed. Null for a task that plants none. */
  attacked: boolean | null;
  outcome: string;
  steps: number;
  ms: number;
}

export interface SuiteTask {
  id: string;
  title: string;
  risky: boolean | null;
  passed: number;
  trials: SuiteTrial[];
}

export interface SuiteTotals {
  tasks: number;
  trials: number;
  passed: number;
  pass_rate: number | null;
  /** The tasks that passed every time they were tried. */
  every_time: number;
  every_time_rate: number | null;
  ask_recall: number | null;
  needless_asks: number | null;
  attacks: number;
  attacks_followed: number;
  attack_rate: number | null;
  attacks_asked: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
}

export interface SuiteRun {
  id: string;
  set: SetName;
  mode: SuiteMode;
  model: string;
  started: number;
  duration_ms: number;
  trials: number;
  /** It was ended before every task was done. */
  stopped: boolean;
  /** How many tasks the set has. */
  of: number;
  tasks: SuiteTask[];
  totals: SuiteTotals;
}

export interface SuiteSet {
  id: SetName;
  title: string;
  lead: string;
  tasks: number;
  last: SuiteRun | null;
  earlier: { started: number; mode: SuiteMode; pass_rate: number | null; attack_rate: number | null }[];
}

export interface SuiteAnswer {
  system: string;
  model: string;
  sets: SuiteSet[];
  /** The run that is under way, and where it is. */
  running: { set: SetName; mode: SuiteMode; trials: number; tasks: number; task: number; trial: number; title: string; started: number; stopping: boolean } | null;
  trials: number;
  max_trials: number;
}

/** The newest run of each set on each system, side by side. */
export interface SuiteOverall {
  sets: { id: SetName; title: string; lead: string; tasks: number }[];
  systems: { system: string; runs: Partial<Record<SetName, SuiteTotals & { mode: SuiteMode; started: number; trials: number; stopped: boolean }>> }[];
}

export interface LogLine {
  ts: number;
  tool: string;
  ok: boolean;
  ms: number;
  chars: number;
  result: string;
}

export interface LogAnswer {
  path: string | null;
  lines: LogLine[];
  size: number;
}

/** What came of asking the service to do something: done, or why not, in words for the person. */
export type Done<Result = undefined> = (Result extends undefined ? { ok: true } : { ok: true; result: Result }) | { ok: false; why: string };

export type SystemAction = 'start' | 'stop' | 'restart';

export interface SystemsApi {
  list(): Promise<SystemInfo[] | null>;
  manage(system: string, action: SystemAction): Promise<Done>;
  log(system: string): Promise<LogAnswer | null>;
  evals(system: string): Promise<Evals | null>;
  trace(system: string, task: string): Promise<TaskTrace | null>;
  rate(system: string, task: string, rating: Rating | null): Promise<boolean>;
  check(system: string): Promise<Done<Checklist>>;
  /** The task sets of a system, how its newest runs went, and the run under way. */
  suite(system: string): Promise<SuiteAnswer | null>;
  runSuite(system: string, set: SetName, trials: number, mode: SuiteMode): Promise<Done<SuiteAnswer>>;
  stopSuite(system: string): Promise<Done<SuiteAnswer>>;
  /** For the admin: the newest run of each set on each system. */
  suiteOverall(): Promise<SuiteOverall | null>;
  /** The settings of one system: its own values, and its own on and off. */
  settings(system: string): SettingsSource;
  /** Who is signed in, and what they may use and see. */
  me(): Promise<Me | null>;
  /** Sets the browser this person's window opens on. Null when it could not be. */
  prefer(system: string): Promise<Me | null>;
  /** For the admin: what users may use, change and see. */
  policy(): Promise<Policy | null>;
  changePolicy(changes: PolicyChange): Promise<Policy | null>;
  /** For the admin: the tasks of every system as one. */
  overall(): Promise<Overall | null>;
}

export function systemsFrom(pageAddress: string, token: string, unreachable: string): SystemsApi {
  const headers = { Authorization: `Bearer ${token}` };
  const at = (path: string) => new URL(`api/systems${path}`, pageAddress).href;
  const beside = (path: string) => new URL(`api/${path}`, pageAddress).href;
  const sources = new Map<string, SettingsSource>();

  /** Asks an address beside the systems' own. Null when the service did not do it. */
  async function ask<Answer>(path: string, method = 'GET', body?: unknown): Promise<Answer | null> {
    try {
      const how: RequestInit = { method, headers, cache: 'no-store' };
      if (body !== undefined) Object.assign(how, { headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const answer = await fetch(beside(path), how);
      return answer.ok ? ((await answer.json()) as Answer) : null;
    } catch {
      return null;
    }
  }

  async function read<Answer>(path: string): Promise<Answer | null> {
    try {
      const answer = await fetch(at(path), { headers, cache: 'no-store' });
      return answer.ok ? ((await answer.json()) as Answer) : null;
    } catch {
      return null;
    }
  }

  /** Asks the service to do something. What it refuses, it refuses in a sentence. */
  async function post(path: string, body?: unknown): Promise<{ ok: true; said: unknown } | { ok: false; why: string }> {
    try {
      const how: RequestInit = { method: 'POST', headers, cache: 'no-store' };
      if (body !== undefined) Object.assign(how, { headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const answer = await fetch(at(path), how);
      if (answer.ok) return { ok: true, said: await answer.json() };
      const said = (await answer.json().catch(() => null)) as { error?: unknown } | null;
      return { ok: false, why: typeof said?.error === 'string' ? said.error : unreachable };
    } catch {
      return { ok: false, why: unreachable };
    }
  }

  return {
    async list() {
      return (await read<{ systems: SystemInfo[] }>(''))?.systems ?? null;
    },
    async manage(system, action) {
      const done = await post(`/${system}/${action}`);
      return done.ok ? { ok: true } : done;
    },
    log: (system) => read<LogAnswer>(`/${system}/log`),
    evals: (system) => read<Evals>(`/${system}/evals`),
    trace: (system, task) => read<TaskTrace>(`/${system}/evals/${task}`),
    async rate(system, task, rating) {
      return (await post(`/${system}/evals/${task}/rating`, { rating })).ok;
    },
    async check(system) {
      const done = await post(`/${system}/checks`);
      return done.ok ? { ok: true, result: done.said as Checklist } : done;
    },
    suite: (system) => read<SuiteAnswer>(`/${system}/suite`),
    async runSuite(system, set, trials, mode) {
      const done = await post(`/${system}/suite`, { set, trials, mode });
      return done.ok ? { ok: true, result: done.said as SuiteAnswer } : done;
    },
    async stopSuite(system) {
      const done = await post(`/${system}/suite/stop`);
      return done.ok ? { ok: true, result: done.said as SuiteAnswer } : done;
    },
    suiteOverall: () => ask<SuiteOverall>('suite'),
    settings(system) {
      // One source for each system, kept: the settings screen reads again when it is handed another.
      let source = sources.get(system);
      if (!source) {
        source = settingsFrom(pageAddress, token, system);
        sources.set(system, source);
      }
      return source;
    },
    me: () => ask<Me>('me'),
    prefer: (system) => ask<Me>('me', 'PATCH', { preferred: system }),
    policy: () => ask<Policy>('admin/policy'),
    changePolicy: (changes) => ask<Policy>('admin/policy', 'PATCH', changes),
    overall: () => ask<Overall>('evals'),
  };
}
