import { W } from '../wording';

const THIS_COMPUTER = new Set(['127.0.0.1', 'localhost', '::1', '[::1]']);

function shortName(host: string): string {
  return host.split('.')[0] ?? host;
}

export interface Systems {
  engine?: string;
  driven?: string;
}

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
