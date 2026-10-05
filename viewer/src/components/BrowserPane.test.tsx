import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DEFAULT_OPTIONS } from '../options';
import type { Box, ServerEvent } from '../protocol';
import { initialState, reduce, type ViewerState } from '../state/reducer';
import { describeState } from '../state/view';
import { BrowserPane } from './BrowserPane';

const T0 = 1_759_480_000;

const started: ServerEvent = {
  type: 'session_started',
  session: 'default',
  agent: 'Claude Code',
  backend: 'remote_headless',
  browser: 'Chromium 153',
  viewport: { width: 1000, height: 500 },
  ts: T0,
};

const BUTTON: Box = { x: 100, y: 50, w: 200, h: 100 };
const FIELD: Box = { x: 600, y: 300, w: 200, h: 100 };

const begins = (step: number, tool: string, target?: Box): ServerEvent => ({ type: 'step_started', step, tool, label: 'Working', target, ts: T0 + step });
const ends = (step: number, ok = true): ServerEvent => ({ type: 'step_finished', step, ok, ms: 40, chars: 90, summary: 'Done', url: 'https://example.com/' });

function show(events: ServerEvent[], showPointer = true) {
  let state: ViewerState = reduce(initialState, { type: 'connection', status: 'connected' });
  state = [started, ...events].reduce((now, event) => reduce(now, { type: 'event', event }), state);
  state = reduce(state, { type: 'frame', src: 'blob:picture', at: T0 });
  const view = describeState(state, T0, DEFAULT_OPTIONS.staleAfterS);
  const { container } = render(
    <BrowserPane state={state} view={view} now={T0} showPointer={showPointer} options={DEFAULT_OPTIONS} onCommand={() => {}} onRelease={() => {}} />,
  );
  return {
    pointer: container.querySelector<HTMLElement>('.agent-pointer'),
    target: container.querySelector<HTMLElement>('.target'),
    click: container.querySelector<HTMLElement>('.click-mark'),
    frame: container.querySelector<HTMLElement>('.frame'),
  };
}

describe("the agent's pointer (spec 9.11)", () => {
  it('is not drawn before the agent has acted on anything', () => {
    const { pointer, target } = show([begins(1, 'browser_navigate'), ends(1)]);
    expect(pointer).toBeNull();
    expect(target).toBeNull();
  });

  it('points at the middle of the element a step names, and the element is outlined', () => {
    const { pointer, target } = show([begins(1, 'browser_click', BUTTON)]);
    // (100 + 200 / 2) of 1000 wide, (50 + 100 / 2) of 500 high.
    expect(pointer?.style.transform).toBe('translate(20%, 20%)');
    expect(target?.dataset.state).toBe('targeting');
    expect(target?.style.left).toBe('10%');
    expect(target?.style.width).toBe('20%');
  });

  it('stays where the agent last acted, through steps that name no element', () => {
    const { pointer, target } = show([begins(1, 'browser_click', BUTTON), ends(1), begins(2, 'browser_snapshot'), ends(2)]);
    expect(pointer?.style.transform).toBe('translate(20%, 20%)');
    expect(target).toBeNull();
  });

  it('moves to the next element', () => {
    const { pointer } = show([begins(1, 'browser_click', BUTTON), ends(1), begins(2, 'browser_type', FIELD)]);
    expect(pointer?.style.transform).toBe('translate(70%, 70%)');
  });

  it('keeps the outline for a moment after the step, and marks a click', () => {
    const { target, click, frame } = show([begins(1, 'browser_click', BUTTON), ends(1)]);
    expect(target?.dataset.state).toBe('acted');
    expect(click?.style.left).toBe('20%');
    expect(click?.style.top).toBe('20%');
    expect(click?.querySelector('.click-ring')).not.toBeNull();
    expect(frame?.style.getPropertyValue('--pointer-hold')).toBe(`${DEFAULT_OPTIONS.pointerHoldMs}ms`);
  });

  it('marks a click only for a click that worked', () => {
    expect(show([begins(1, 'browser_type', FIELD), ends(1)]).click).toBeNull();
    const failed = show([begins(1, 'browser_click', BUTTON), ends(1, false)]);
    expect(failed.click).toBeNull();
    expect(failed.target?.dataset.state).toBe('failed');
  });

  it('is not drawn while the click is still under way', () => {
    expect(show([begins(1, 'browser_click', BUTTON)]).click).toBeNull();
  });

  it('draws nothing when the person has turned the pointer off', () => {
    const { pointer, target, click } = show([begins(1, 'browser_click', BUTTON), ends(1)], false);
    expect(pointer).toBeNull();
    expect(target).toBeNull();
    expect(click).toBeNull();
  });

  it('glows at the edge of the browser while the agent works, and not while a person drives', () => {
    const glow = (events: ServerEvent[]) => {
      let state: ViewerState = reduce(initialState, { type: 'connection', status: 'connected' });
      state = [started, ...events].reduce((now, event) => reduce(now, { type: 'event', event }), state);
      state = reduce(state, { type: 'frame', src: 'blob:picture', at: T0 });
      const view = describeState(state, T0, DEFAULT_OPTIONS.staleAfterS);
      const { container } = render(<BrowserPane state={state} view={view} now={T0} showPointer options={DEFAULT_OPTIONS} onCommand={() => {}} onRelease={() => {}} />);
      return container.querySelector('.frame-glow');
    };
    expect(glow([begins(1, 'browser_click', BUTTON)])).not.toBeNull();
    expect(glow([{ type: 'control_changed', state: 'person', since: T0 }])).toBeNull();
    expect(glow([{ type: 'control_changed', state: 'paused', since: T0 }])).toBeNull();
  });

  it('draws nothing while a person drives', () => {
    const { pointer, target } = show([begins(1, 'browser_click', BUTTON), ends(1), { type: 'control_changed', state: 'person', since: T0 + 5 }]);
    expect(pointer).toBeNull();
    expect(target).toBeNull();
  });
});
