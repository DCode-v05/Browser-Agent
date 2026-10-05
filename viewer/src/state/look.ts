// What a page of the browser shows about who is driving, when the browser is a window on the
// person's own screen and the viewer is the chat in the extension's side panel (spec 9.15). The
// extension draws it; the viewer decides it, so the page and the chat never disagree.

import type { Box } from '../protocol';
import type { Step, ViewerState } from './reducer';
import type { StateView, Tone } from './view';

export const LOOK = 'bap-browser.look';

export interface Look {
  type: typeof LOOK;
  /** 'none' when the page shows nothing: no live session, or an agent that waits for a task. */
  tone: Tone;
  /** The edge of the page breathes while the agent works. */
  working: boolean;
  label: string;
  detail: string;
  /** The element the agent is acting on now, in the page's own pixels. */
  target: Box | null;
  /** Where the agent's pointer is. It stays where the agent last acted. */
  pointer: { x: number; y: number } | null;
  /** The number of the step whose click is marked, once. */
  click: number | null;
}

/** The tools that press a mouse button. */
const CLICKS = new Set(['browser_click']);
/** The states in which nothing is known for sure, or there is nothing to show. */
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

/** The token that holds a tone's colour. */
function colourToken(tone: Tone): string {
  return tone === 'neutral' ? '--border-strong' : `--${tone}`;
}

/**
 * Tells the page that shows this viewer in a frame, which is the extension's side panel, what the
 * browser's pages are to show. The colours go with it, so the page follows the viewer's theme.
 */
export function tellPanel(look: Look, panel: Pick<Window, 'postMessage'> = window.parent, root: Element = document.documentElement): void {
  const styles = getComputedStyle(root);
  const colour = look.tone === 'none' ? '' : styles.getPropertyValue(colourToken(look.tone)).trim();
  const onColour = styles.getPropertyValue('--surface').trim();
  // The frame's parent is whoever the service allows to show the viewer; its origin is named when the browser tells it.
  const to = window.location.ancestorOrigins?.[0] ?? '*';
  panel.postMessage({ ...look, colour, onColour }, to);
}
