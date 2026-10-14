import { describe, expect, it } from 'vitest';

import { W } from './wording';
import { wordsFor } from './words';

/** Every string of a tree of words, with the path that leads to it. */
function strings(of: unknown, path = ''): [string, string][] {
  if (typeof of === 'string') return [[path, of]];
  if (typeof of === 'function') return [[path, String((of as (...given: string[]) => unknown)('a', 'b', 'c'))]];
  if (of && typeof of === 'object') return Object.entries(of).flatMap(([key, value]) => strings(value, `${path}.${key}`));
  return [];
}

describe('the words of a page of computer use', () => {
  const desktop = wordsFor('contained_desktop');

  it('a browser keeps the words as they are', () => {
    expect(wordsFor('remote_headless')).toBe(W);
    expect(wordsFor(undefined)).toBe(W);
  });

  it('the controls of the chat speak of the desktop, and of carrying on from the last task', () => {
    expect(desktop.buttons.hint.task).toBe('Type what the agent should do on this desktop, then press Enter. A new task carries on from where the last one ended.');
    expect(desktop.buttons.hint.takeOver).toContain('the desktop');
    expect(desktop.parts.browser).toBe('Desktop');
    expect(desktop.studio.hint.view.agent).toBe('The desktop itself, live, and the chat with the agent.');
    expect(desktop.systems.evals.step('1 s', '2 s')).toBe('A step on the desktop: 1 s typical, 2 s slow');
  });

  it('what a page of computer use shows of itself never says browser', () => {
    const shown = [desktop.buttons, desktop.parts, desktop.topBar, desktop.frame.alt, desktop.studio.hint.view, desktop.systems.panel.lead, desktop.systems.logLead, desktop.systems.recordsLead, desktop.systems.evals, desktop.systems.suite.runReferenceHint, desktop.stop, desktop.takeover];
    const wrong = shown.flatMap((part) => strings(part)).filter(([path, text]) => /browser/i.test(text) && !path.includes('checklist'));
    expect(wrong).toEqual([]);
  });

  it('names the product with what the page is for: computer use', () => {
    expect(desktop.product).toBe('bap-browser · Computer use');
    expect(wordsFor('remote_headless').product).toBe('bap-browser');
  });

  it('words that are not overridden are the same as a browser has', () => {
    expect(desktop.buttons.close).toBe(W.buttons.close);
    expect(desktop.signIn).toBe(W.signIn);
  });
});
