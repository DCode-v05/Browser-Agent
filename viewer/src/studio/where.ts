// Where the computer page's engine runs, and what it works on (spec 22.6). Said on the page, so that
// a person with several such pages open knows which is which.

import { W } from '../wording';

/** The service's own machine, when the page was opened on it. */
const THIS_COMPUTER = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

/** A machine's short name: the first part of its address, as a tailnet names it. */
function shortName(host: string): string {
  return host.split('.')[0] ?? host;
}

export function whereItWorks(runs: string | undefined, pageHost: string, helperUrl: string): { engine: string; target: string } {
  const words = W.studio.where;
  const engine = THIS_COMPUTER.has(pageHost) ? words.thisComputer : shortName(pageHost);
  let helper = '';
  try {
    helper = helperUrl ? shortName(new URL(helperUrl).hostname) : '';
  } catch {
    // Not an address: the machine is not named.
  }
  const target =
    runs === 'remote'
      ? helper && !THIS_COMPUTER.has(helper)
        ? words.remoteNamed(helper)
        : words.remote
      : runs === 'here'
        ? words.here
        : runs === 'machine'
          ? words.machine
          : words.container;
  return { engine, target };
}
