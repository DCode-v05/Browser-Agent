// The settings answer (spec 10.2). The settings screen is drawn from it; the viewer holds no
// list of settings of its own.

import type { Surface } from '../protocol';

export type SettingControl = 'choice' | 'select' | 'switch' | 'list' | 'action' | 'path' | 'about';
export type SettingValue = string | boolean | string[] | null;

export interface SettingChoice {
  value: string;
  label: string;
  /** A few words under the label. */
  hint?: string;
  /** Shown, but it would loosen what the deployment requires. */
  disabled?: boolean;
}

export interface Setting {
  id: string;
  title: string;
  /** One line saying what it does. */
  description: string;
  control: SettingControl;
  choices?: SettingChoice[];
  value: SettingValue;
  default: SettingValue;
  /** Entries of a list that the deployment set. A person cannot remove them. */
  fixed?: string[];
  locked: boolean;
  applies: 'now' | 'next_session';
  /** For a browser among several: whether a change is that browser's alone, or every browser's. */
  scope?: 'system' | 'all';
  /** The label of an action's button. */
  action?: string;
  /** An action that cannot be undone asks first. */
  confirm?: { question: string; consequence: string; button: string };
}

export interface SettingsGroup {
  id: string;
  title: string;
  settings: Setting[];
}

export interface SettingsAnswer {
  surface: Surface;
  /** The browser these settings are of, where the service has several (spec 9.17). */
  system?: string;
  /** Whose settings these are: the admin's configuration, or a user's own (spec 4.11). */
  role?: 'admin' | 'user';
  groups: SettingsGroup[];
}

export type RefusalReason = 'locked' | 'not_on_this_surface' | 'would_loosen' | 'not_a_choice' | 'bad_site';

export type ChangeResult = { ok: true; answer: SettingsAnswer } | { ok: false; setting: string; reason: RefusalReason };

export interface ConfigAnswer {
  version: string;
  browser: string;
  /** Every configuration value that differs from its default, with where it came from. */
  changed: { key: string; value: string; source: string }[];
}

export interface SettingsSource {
  load(surface: Surface): Promise<SettingsAnswer>;
  change(surface: Surface, changes: Record<string, SettingValue>): Promise<ChangeResult>;
  /** Runs an action setting, such as clearing browsing data. */
  run(surface: Surface, action: string): Promise<void>;
  config(): Promise<ConfigAnswer>;
}
