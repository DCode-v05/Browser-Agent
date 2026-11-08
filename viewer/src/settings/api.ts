import type { Surface } from '../protocol';
import type { ChangeResult, ConfigAnswer, SettingsAnswer, SettingsSource, SettingValue } from './types';

export class SettingsUnreachable extends Error {}

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
      if (answer.status === 409) return { ok: false, ...((await answer.json()) as Pick<Extract<ChangeResult, { ok: false }>, 'setting' | 'reason'>) };
      throw new SettingsUnreachable('api/settings');
    },

    async run(_surface: Surface, action: string): Promise<void> {
      if (action !== 'clear_browsing_data') return;
      const answer = await ask('api/browsing-data/clear', { method: 'POST' });
      if (!answer.ok) throw new SettingsUnreachable('api/browsing-data/clear');
    },

    config: () => read<ConfigAnswer>('api/config'),
  };
}
