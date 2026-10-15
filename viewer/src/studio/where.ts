// Where the computer page's engine runs, and what it works on (spec 22.6). Said on the page, so that
// a person with several such pages open knows which is which.

import { W } from '../wording';

/** The service's own machine, when the page was opened on it. */
const THIS_COMPUTER = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

/** A machine's short name: the first part of its address, as a tailnet names it. */
function shortName(host: string): string {
  return host.split('.')[0] ?? host;
}

/** The systems a page was told: the engine's own, and the machine's it controls. */
export interface Systems {
  engine?: string;
  driven?: string;
}

/** The engine's machine, as the mark on every page names it: by the page's address, with its system. */
export function engineName(pageHost: string, system: string | undefined): string {
  const words = W.studio.where;
  const named = system ? words.systems[system] : undefined;
  const machine = THIS_COMPUTER.has(pageHost) ? words.thisComputer : shortName(pageHost);
  return named ? `${machine} (${named})` : machine;
}

export function whereItWorks(runs: string | undefined, pageHost: string, helperUrl: string, systems: Systems = {}): { engine: string; target: string } {
  const words = W.studio.where;
  const drivenSystem = systems.driven ? words.systems[systems.driven] : undefined;
  const withSystem = (name: string, system: string | undefined) => (system ? `${name} (${system})` : name);
  const engine = engineName(pageHost, systems.engine);
  let helper = '';
  try {
    helper = helperUrl ? shortName(new URL(helperUrl).hostname) : '';
  } catch {
    // Not an address: the machine is not named.
  }
  const target =
    runs === 'remote'
      ? helper && !THIS_COMPUTER.has(helper)
        ? words.remoteNamed(withSystem(helper, drivenSystem))
        : words.remote
      : runs === 'here'
        ? words.here
        : runs === 'machine'
          ? words.machine(drivenSystem)
          : words.container;
  return { engine, target };
}
