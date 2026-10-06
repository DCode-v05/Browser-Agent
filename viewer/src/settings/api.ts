// The settings of a live session, read from and saved to the service (spec 10.2). The token goes in a
// header, never in the address.

import type { Surface } from '../protocol';
import type { ChangeResult, ConfigAnswer, SettingsAnswer, SettingsSource, SettingValue } from './types';

/** The service did not answer, or answered with something that is not the settings. */
export class SettingsUnreachable extends Error {}

export function settingsFrom(pageAddress: string, token: string): SettingsSource {
  const headers = { Authorization: `Bearer ${token}` };
  const at = (path: string) => new URL(path, pageAddress).href;

  async function ask(path: string, how: RequestInit = {}): Promise<Response> {
    try {
      return await fetch(at(path), { cache: 'no-store', ...how, headers: { ...headers, ...how.headers } });
    } catch {
      throw new SettingsUnreachable(path);
    }
  }

  async function read<Answer>(path: string): Promise<Answer> {
    const answer = await ask(path);
    if (!answer.ok) throw new SettingsUnreachable(path);
    return (await answer.json()) as Answer;
  }

  return {
    load: (surface: Surface) => read<SettingsAnswer>(`api/settings?surface=${encodeURIComponent(surface)}`),

    async change(surface: Surface, changes: Record<string, SettingValue>): Promise<ChangeResult> {
      const answer = await ask('api/settings', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ surface, changes }) });
      if (answer.ok) return { ok: true, answer: (await answer.json()) as SettingsAnswer };
      // A change the person may not make: the service says which setting, and why.
      if (answer.status === 409) return { ok: false, ...((await answer.json()) as Pick<Extract<ChangeResult, { ok: false }>, 'setting' | 'reason'>) };
      throw new SettingsUnreachable('api/settings');
    },

    // This build has no setting that is an action.
    run: async () => undefined,

    config: () => read<ConfigAnswer>('api/config'),
  };
}
