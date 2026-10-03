// Steps become timeline rows (spec 9.7): one sentence per step, consecutive reads collapsed into
// one row with a count, and a divider where the session sat idle.

import type { Step } from './reducer';

const READ_TOOLS = new Set(['browser_snapshot', 'browser_get_text']);

export type Row =
  | {
      kind: 'step';
      key: string;
      /** The step the row stands for; the newest one when several are collapsed. */
      step: Step;
      steps: Step[];
      text: string;
      count: number;
      ms?: number;
      status: Step['status'];
    }
  | { kind: 'idle'; key: string; seconds: number };

function endOf(step: Step): number {
  return step.startedAt + (step.ms ?? 0) / 1000;
}

function isQuietRead(step: Step): boolean {
  return READ_TOOLS.has(step.tool) && step.status === 'ok';
}

export function buildRows(steps: Step[], idleDividerS: number): Row[] {
  const rows: Row[] = [];
  let previous: Step | undefined;
  for (const step of steps) {
    const gap = previous ? step.startedAt - endOf(previous) : 0;
    const idle = gap >= idleDividerS;
    if (idle) rows.push({ kind: 'idle', key: `idle-${step.n}`, seconds: Math.floor(gap) });

    const last = rows.at(-1);
    if (!idle && last?.kind === 'step' && isQuietRead(step) && last.steps.every(isQuietRead)) {
      last.steps.push(step);
      last.step = step;
      last.count += 1;
      last.ms = (last.ms ?? 0) + (step.ms ?? 0);
    } else {
      rows.push({
        kind: 'step',
        // Keyed by its first step, so the row keeps its identity while later reads join it.
        key: `step-${step.n}`,
        step,
        steps: [step],
        text: step.summary ?? step.label,
        count: 1,
        ms: step.ms,
        status: step.status,
      });
    }
    previous = step;
  }
  return rows;
}

export function formatDuration(ms: number): string {
  if (ms < 1) return 'under 1 ms';
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 10_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms / 1000)} s`;
}

export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = String(total % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${rest}` : `${minutes}:${rest}`;
}

export function formatCount(count: number): string {
  return count.toLocaleString('en-US');
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
