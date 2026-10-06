// The browsers of the window as systems (spec 9.17): what the service says of each, and what a
// person may ask it to do with one. The token goes in a header, never in the address.

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
  /** Where this browser's log is written. Null when a person turned it off. */
  log: string | null;
  /** The folder that holds the record of this browser's tasks. */
  records: string;
  note?: string;
}

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
  cost: { tasks_counted: number; input_tokens: number; output_tokens: number; usd: number | null; usd_per_task: number | null };
  recent: TaskRow[];
  checklist: Checklist | null;
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
  /** The settings of one system: its own values, and its own on and off. */
  settings(system: string): SettingsSource;
}

export function systemsFrom(pageAddress: string, token: string, unreachable: string): SystemsApi {
  const headers = { Authorization: `Bearer ${token}` };
  const at = (path: string) => new URL(`api/systems${path}`, pageAddress).href;
  const sources = new Map<string, SettingsSource>();

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
    settings(system) {
      // One source for each system, kept: the settings screen reads again when it is handed another.
      let source = sources.get(system);
      if (!source) {
        source = settingsFrom(pageAddress, token, system);
        sources.set(system, source);
      }
      return source;
    },
  };
}
