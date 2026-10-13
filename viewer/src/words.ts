// The words a page is drawn from (spec 9.6, 22.3). A browser's page has `W`. The page of computer
// use has the same words, with the desktop's own where a browser's would say "browser".

import { createContext, useContext } from 'react';

import type { Backend } from './protocol';
import { ON_A_DESKTOP, W, type Words } from './wording';

function withThese(words: unknown, these: unknown): unknown {
  if (these === undefined) return words;
  if (typeof these !== 'object' || these === null) return these;
  const whole = { ...(words as Record<string, unknown>) };
  for (const [name, part] of Object.entries(these)) whole[name] = withThese(whole[name], part);
  return whole;
}

const OF_A_DESKTOP = withThese(W, ON_A_DESKTOP) as Words;

/** The words of a system's page. With no system, a browser's. */
export function wordsFor(backend: Backend | undefined): Words {
  return backend === 'contained_desktop' ? OF_A_DESKTOP : W;
}

export const TheWords = createContext<Words>(W);

/** The words of the page this part is drawn in. */
export function useWords(): Words {
  return useContext(TheWords);
}
