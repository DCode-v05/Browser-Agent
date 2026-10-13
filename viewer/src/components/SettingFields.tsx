// The settings a person types: a list of sites, and one web address.

import { useId, useState } from 'react';

import type { Setting, SettingValue } from '../settings/types';
import { W } from '../wording';
import { Icon } from './Icon';

export function SiteList({ setting, labelledBy, onSave, lockedWords }: { setting: Setting; labelledBy: string; onSave(value: SettingValue): Promise<boolean>; lockedWords: string }) {
  const saved = Array.isArray(setting.value) ? setting.value.join('\n') : '';
  const [text, setText] = useState(saved);
  const hintId = useId();
  return (
    <div className="site-list">
      {setting.fixed && setting.fixed.length > 0 && (
        <ul className="fixed-sites" aria-label={lockedWords}>
          {setting.fixed.map((site) => (
            <li key={site} className="fixed-site">
              <Icon name="lock" />
              <span>{site}</span>
            </li>
          ))}
        </ul>
      )}
      <textarea
        className="sites"
        rows={3}
        spellCheck={false}
        aria-labelledby={labelledBy}
        aria-describedby={hintId}
        value={text}
        disabled={setting.locked}
        onChange={(event) => setText(event.target.value)}
        // What was typed stays in the box when it is refused, so it can be corrected.
        onBlur={() => {
          if (text !== saved) void onSave(text.split('\n').map((line) => line.trim()).filter(Boolean));
        }}
      />
      <p className="setting-hint" id={hintId}>
        {W.settings.listHint}
      </p>
    </div>
  );
}

export function AddressField({ setting, labelledBy, describedBy, onSave }: { setting: Setting; labelledBy: string; describedBy: string; onSave(value: SettingValue): Promise<boolean> }) {
  const saved = typeof setting.value === 'string' ? setting.value : '';
  const [text, setText] = useState(saved);
  return (
    <input
      type="url"
      className="sites one-line"
      spellCheck={false}
      aria-labelledby={labelledBy}
      aria-describedby={describedBy}
      value={text}
      disabled={setting.locked}
      onChange={(event) => setText(event.target.value)}
      // What was typed stays in the field when it is refused, so it can be corrected.
      onBlur={() => {
        if (text.trim() !== saved) void onSave(text.trim());
      }}
    />
  );
}
