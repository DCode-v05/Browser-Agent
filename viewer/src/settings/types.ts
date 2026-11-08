import type { Surface } from '../protocol';

export type SettingControl = 'choice' | 'select' | 'switch' | 'list' | 'address' | 'action' | 'path' | 'about';
export type SettingValue = string | boolean | string[] | null;

export interface SettingChoice {
  value: string;
  label: string;
  hint?: string;
  disabled?: boolean;
}

export interface Setting {
  id: string;
  title: string;
  description: string;
  control: SettingControl;
  choices?: SettingChoice[];
  value: SettingValue;
  default: SettingValue;
  fixed?: string[];
  locked: boolean;
  applies: 'now' | 'next_session';
  scope?: 'system' | 'all';
  action?: string;
  confirm?: { question: string; consequence: string; button: string };
}

export interface SettingsGroup {
  id: string;
  title: string;
  settings: Setting[];
}

export interface SettingsAnswer {
  surface: Surface;
  system?: string;
  role?: 'admin' | 'user';
  groups: SettingsGroup[];
}

export type RefusalReason = 'locked' | 'not_on_this_surface' | 'would_loosen' | 'not_a_choice' | 'bad_site' | 'bad_address';

export type ChangeResult = { ok: true; answer: SettingsAnswer } | { ok: false; setting: string; reason: RefusalReason };

export interface ConfigAnswer {
  version: string;
  browser: string;
  changed: { key: string; value: string; source: string }[];
}

export interface SettingsSource {
  load(surface: Surface): Promise<SettingsAnswer>;
  change(surface: Surface, changes: Record<string, SettingValue>): Promise<ChangeResult>;
  run(surface: Surface, action: string): Promise<void>;
  config(): Promise<ConfigAnswer>;
}
