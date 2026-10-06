// The settings of a live session, read from and saved to the service (spec 10.2). The token goes in a
// header, never in the address.

import type { Surface } from '../protocol';
import type { ChangeResult, ConfigAnswer, SettingsAnswer, SettingsSource, SettingValue } from './types';

/** The service did not answer, or answered with something that is not the settings. */
export class SettingsUnreachable extends Error {}

/** `system` names one browser of a window that has several: the settings are then that browser's own (spec 9.17). */
export function settingsFrom(pageAddress: string, token: string, system?: string): SettingsSource {
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
    load: (surface: Surface) => read<SettingsAnswer>(`api/settings?surface=${encodeURIComponent(surface)}${system ? `&system=${encodeURIComponent(system)}` : ''}`),

    async change(surface: Surface, changes: Record<string, SettingValue>): Promise<ChangeResult> {
      const answer = await ask('api/settings', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(system ? { surface, system, changes } : { surface, changes }) });
      if (answer.ok) return { ok: true, answer: (await answer.json()) as SettingsAnswer };
      // A change the person may not make: the service says which setting, and why.
      if (answer.status === 409) return { ok: false, ...((await answer.json()) as Pick<Extract<ChangeResult, { ok: false }>, 'setting' | 'reason'>) };
      throw new SettingsUnreachable('api/settings');
    },

    // The one setting that is an action. The service ends the cloud browser's sessions and deletes its data.
    async run(_surface: Surface, action: string): Promise<void> {
      if (action !== 'clear_browsing_data') return;
      const answer = await ask('api/browsing-data/clear', { method: 'POST' });
      if (!answer.ok) throw new SettingsUnreachable('api/browsing-data/clear');
    },

    config: () => read<ConfigAnswer>('api/config'),
  };
}
