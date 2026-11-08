import type { Box } from '../protocol';
import type { Step, ViewerState } from './reducer';
import type { StateView, Tone } from './view';

export const LOOK = 'bap-browser.look';

export interface Look {
  type: typeof LOOK;
  tone: Tone;
  working: boolean;
  label: string;
  detail: string;
  target: Box | null;
  pointer: { x: number; y: number } | null;
  click: number | null;
}

const CLICKS = new Set(['browser_click']);
const NOTHING_TO_SHOW = new Set(['no_agent', 'ended', 'disconnected', 'refused']);

const NOTHING: Look = { type: LOOK, tone: 'none', working: false, label: '', detail: '', target: null, pointer: null, click: null };

function lastTarget(steps: readonly Step[]): Box | undefined {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const target = steps[index]?.target;
    if (target) return target;
  }
  return undefined;
}

export function lookOf(state: ViewerState, view: StateView, showPointer: boolean): Look {
  const resting = view.key === 'agent' && !view.working;
  if (!state.session || NOTHING_TO_SHOW.has(view.key) || resting || view.tone === 'none') return NOTHING;
  const last = state.steps.at(-1);
  const acting = showPointer && (view.key === 'agent' || view.key === 'paused' || view.key === 'waiting_approval');
  const at = acting ? lastTarget(state.steps) : undefined;
  return {
    type: LOOK,
    tone: view.tone,
    working: view.working,
    label: view.label,
    detail: view.working ? view.detail : '',
    target: (acting && last?.status === 'running' && last.target) || null,
    pointer: at ? { x: at.x + at.w / 2, y: at.y + at.h / 2 } : null,
    click: acting && last?.status === 'ok' && last.target && CLICKS.has(last.tool) ? last.n : null,
  };
}

function colourToken(tone: Tone): string {
  return tone === 'neutral' ? '--border-strong' : `--${tone}`;
}

export function tellPanel(look: Look, panel: Pick<Window, 'postMessage'> = window.parent, root: Element = document.documentElement): void {
  const styles = getComputedStyle(root);
  const colour = look.tone === 'none' ? '' : styles.getPropertyValue(colourToken(look.tone)).trim();
  const onColour = styles.getPropertyValue('--surface').trim();
  const to = window.location.ancestorOrigins?.[0] ?? '*';
  panel.postMessage({ ...look, colour, onColour }, to);
}
