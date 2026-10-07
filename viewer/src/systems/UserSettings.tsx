// A user's own settings for one browser (spec 4.11): which browser they prefer, and every setting
// the admin lets users have, each with what it does and a control that works. What the admin holds
// is said in words, not drawn as a control that does nothing.

import { useId, useState } from 'react';

import { Button } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { SettingsAnswer } from '../settings/types';
import { W } from '../wording';
import type { LogAnswer, Me, SystemInfo, SystemsApi } from './api';
import { CardHead, LogLines } from './parts';
import { SettingsList } from './SettingsList';

interface Props {
  system: SystemInfo;
  /** The browsers this person may use, to choose the preferred one among. */
  systems: SystemInfo[];
  api: SystemsApi;
  surface: Surface;
  word: string;
  me: Me;
  /** Goes up when the service has been asked again: what the admin changed since shows then. */
  version: number;
  /** The person chose the browser their window opens on. */
  onPrefer(system: string): void;
  /** Told what the settings are after one was changed here. */
  onSettings?(answer: SettingsAnswer): void;
  onToast(text: string): void;
}

export function UserSettings({ system, systems, api, surface, word, me, version, onPrefer, onSettings, onToast }: Props) {
  const U = W.systems.user;
  const source = api.settings(system.id);
  const [log, setLog] = useState<LogAnswer | null>(null);
  const preferId = useId();

  const name = W.backend[system.backend];
  return (
    <article className="system-card" aria-label={name}>
      <CardHead system={system} word={word} />

      <div className="system-row">
        <label className="system-row-name" htmlFor={preferId}>
          {U.preferred}
          <span className="system-row-hint">{U.preferredLead}</span>
          {me.preferred === system.id && <span className="system-row-hint">{U.isPreferred}</span>}
        </label>
        <select id={preferId} className="select" value={me.preferred ?? ''} onChange={(event) => onPrefer(event.target.value)}>
          {systems.map((one) => (
            <option key={one.id} value={one.id}>
              {W.backend[one.backend]}
            </option>
          ))}
        </select>
      </div>

      <SettingsList source={source} surface={surface} version={version} lockedWords={U.fixed} refused={U.refused} noteFor={(setting) => (setting.scope === 'all' ? U.everyBrowser : undefined)} onChanged={onSettings} onToast={onToast} />

      {system.log && (
        <>
          <h4 className="system-section">{W.systems.log}</h4>
          <div className="system-actions">
            <Button hint={W.systems.logHint} onClick={async () => setLog(log ? null : await api.log(system.id))}>
              {log ? W.systems.logHide : W.systems.logShow}
            </Button>
          </div>
          {log && <LogLines log={log} />}
        </>
      )}
    </article>
  );
}
