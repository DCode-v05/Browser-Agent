// Keeps Tab inside a dialog, so a person using the keyboard does not fall out of it into the page behind.

import type { KeyboardEvent } from 'react';

const FOCUSABLE = 'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

/** Whether a person can see the element. Where the browser cannot say, it is taken as shown. */
export function isShown(element: Element): boolean {
  return typeof element.checkVisibility !== 'function' || element.checkVisibility();
}

export function trapTab(event: KeyboardEvent<HTMLElement>): void {
  if (event.key !== 'Tab') return;
  const items = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(isShown);
  if (items.length === 0) return;
  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
