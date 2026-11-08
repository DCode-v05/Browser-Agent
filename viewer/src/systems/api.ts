import type { Role } from '../auth/api';
import type { Backend } from '../protocol';
import { settingsFrom } from '../settings/api';
import type { SettingsSource } from '../settings/types';

export interface SystemInfo {
  id: string;
  backend: Backend;
  state: string;
  enabled: boolean;
  working: boolean;
  attention: boolean;
  model: string;
  log?: string | null;
  records?: string;
  note?: string;
  runs?: string;
}

export type Seen = 'evaluations' | 'cost' | 'traces' | 'checklist' | 'log';

export interface Me {
  role: Role;
  systems: string[];
  preferred: string | null;
  sees: Record<Seen, boolean>;
}

export interface PolicyLine {
  id: string;
  title?: string;
  description?: string;
  allowed: boolean;
}

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
  cost: Cost | null;
  recent: TaskRow[];
  checklist: Checklist | null;
  may?: { cost: boolean; traces: boolean; checklist: boolean };
}

export interface Cost {
  tasks_counted: number;
  input_tokens: number;
  output_tokens: number;
  usd: number | null;
  usd_per_task: number | null;
}

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

export interface Overall {
  tasks: Evals['tasks'];
  latency: Evals['latency'];
  time: Evals['time'];
  cost: Cost;
  systems: OverallLine[];
}

export type SetName = 'short' | 'confirm' | 'attack' | 'long' | 'infeasible';
export type SuiteMode = 'agent' | 'reference';

export interface SuiteTrial {
  passed: boolean;
  why: string;
  asked: number;
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
  errors?: number;
  passed: number;
  pass_rate: number | null;
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
  stopped: boolean;
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
  running: { set: SetName; mode: SuiteMode; trials: number; tasks: number; task: number; trial: number; title: string; started: number; stopping: boolean } | null;
  trials: number;
  max_trials: number;
}

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

export type Done<Result = undefined> = (Result extends undefined ? { ok: true } : { ok: true; result: Result }) | { ok: false; why: string };

export type SystemAction = 'start' | 'stop' | 'restart' | 'install' | 'allow';

export interface SystemsApi {
  list(): Promise<SystemInfo[] | null>;
  manage(system: string, action: SystemAction): Promise<Done>;
  log(system: string): Promise<LogAnswer | null>;
  evals(system: string): Promise<Evals | null>;
  trace(system: string, task: string): Promise<TaskTrace | null>;
  rate(system: string, task: string, rating: Rating | null): Promise<boolean>;
  check(system: string): Promise<Done<Checklist>>;
  suite(system: string): Promise<SuiteAnswer | null>;
  runSuite(system: string, set: SetName, trials: number, mode: SuiteMode): Promise<Done<SuiteAnswer>>;
  stopSuite(system: string): Promise<Done<SuiteAnswer>>;
  suiteOverall(): Promise<SuiteOverall | null>;
  settings(system: string): SettingsSource;
  me(): Promise<Me | null>;
  prefer(system: string): Promise<Me | null>;
  policy(): Promise<Policy | null>;
  changePolicy(changes: PolicyChange): Promise<Policy | null>;
  overall(): Promise<Overall | null>;
}

export function systemsFrom(pageAddress: string, token: string, unreachable: string): SystemsApi {
  const headers = { Authorization: `Bearer ${token}` };
  const at = (path: string) => new URL(`api/systems${path}`, pageAddress).href;
  const beside = (path: string) => new URL(`api/${path}`, pageAddress).href;
  const sources = new Map<string, SettingsSource>();

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
