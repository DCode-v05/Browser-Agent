import type { SettingsAnswer } from './settings/types';

export interface Preferences {
  colourMode: 'system' | 'light' | 'dark';
  showAgentPointer: boolean;
}

export const DEFAULT_PREFERENCES: Preferences = { colourMode: 'system', showAgentPointer: true };

export function preferencesFrom(answer: SettingsAnswer): Preferences {
  const value = (id: string) => answer.groups.flatMap((group) => group.settings).find((setting) => setting.id === id)?.value;
  const mode = value('colour_mode');
  return {
    colourMode: mode === 'light' || mode === 'dark' ? mode : 'system',
    showAgentPointer: value('show_agent_pointer') !== false,
  };
}
