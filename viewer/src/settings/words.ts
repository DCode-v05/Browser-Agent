// A setting's value in the words a person reads.

import { W } from '../wording';
import type { Setting } from './types';

/** What a setting is set to, in the words its choices use. */
export function valueInWords(setting: Setting): string {
  if (typeof setting.value === 'boolean') return setting.value ? W.settings.on : W.settings.off;
  if (Array.isArray(setting.value)) return W.systems.sites(setting.value.length + (setting.fixed?.length ?? 0));
  return setting.choices?.find((choice) => choice.value === setting.value)?.label ?? String(setting.value ?? '');
}
