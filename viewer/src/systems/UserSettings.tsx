// A user's own settings for one browser (spec 4.11): which browser they prefer, and the settings
// the admin lets users change. What the admin has fixed is said in words, not drawn as a switch
// that does nothing.

import { useEffect, useId, useState } from 'react';

import { SettingsScreen } from '../components/SettingsScreen';
import { Button } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { Setting, SettingsAnswer, SettingValue } from '../settings/types';
import { W } from '../wording';
import type { LogAnswer, Me, SystemInfo, SystemsApi } from './api';
import { CardHead, chosen, LogLines, Switch } from './parts';

interface Props {
  system: SystemInfo;
  /** The browsers this person may use, to choose the preferred one among. */
  systems: SystemInfo[];
  api: SystemsApi;
  surface: Surface;
  word: string;
  me: Me;
  /** The person chose the browser their window opens on. */
  onPrefer(system: string): void;
  onToast(text: string): void;
}

export function UserSettings({ system, systems, api, surface, word, me, onPrefer, onToast }: Props) {
  const U = W.systems.user;
  const source = api.settings(system.id);
  const [answer, setAnswer] = useState<SettingsAnswer | null>(null);
  const [note, setNote] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [log, setLog] = useState<LogAnswer | null>(null);
  const preferId = useId();

  useEffect(() => {
    let current = true;
    source.load(surface).then(
      (loaded) => current && setAnswer(loaded),
      () => current && setNote(W.systems.unreachable),
    );
    return () => {
      current = false;
    };
  }, [source, surface]);

  const all = answer?.groups.flatMap((group) => group.settings) ?? [];
  // Theirs to change, and fixed by the admin: the two are not drawn alike.
  const switches = all.filter((setting) => setting.control === 'switch' && !setting.locked);
  const choices = all.filter((setting) => (setting.control === 'choice' || setting.control === 'select') && !setting.locked);
  // A list of sites is typed in the settings screen: the card says how many there are.
  const others = all.filter((setting) => !switches.includes(setting) && !choices.includes(setting) && !setting.locked);
  const fixed = all.filter((setting) => setting.locked);

  async function change(setting: Setting, value: SettingValue) {
    setNote('');
    try {
      const result = await source.change(surface, { [setting.id]: value });
      if (result.ok) setAnswer(result.answer);
      else setNote(U.refused[result.reason]);
    } catch {
      setNote(W.settings.notSaved);
    }
  }

  const name = W.backend[system.backend];
  return (
    <article className="system-card" aria-label={name}>
      <CardHead system={system} word={word} />

      <div className="system-row">
        <label className="system-row-name" htmlFor={preferId}>
          {U.preferred}
          <span className="system-locked">{me.preferred === system.id ? U.isPreferred : U.preferredLead}</span>
        </label>
        <select id={preferId} className="select" value={me.preferred ?? ''} onChange={(event) => onPrefer(event.target.value)}>
          {systems.map((one) => (
            <option key={one.id} value={one.id}>
              {W.backend[one.backend]}
            </option>
          ))}
        </select>
      </div>
      {note && (
        <p className="system-note" role="status">
          {note}
        </p>
      )}

      {switches.length > 0 && (
        <>
          <h4 className="system-section">{U.yours}</h4>
          <ul className="system-list">
            {switches.map((setting) => (
              <li key={setting.id} className="system-row">
                <span className="system-row-name">{setting.title}</span>
                <Switch label={`${setting.title}: ${name}`} on={setting.value === true} onChange={(next) => void change(setting, next)} />
              </li>
            ))}
          </ul>
        </>
      )}

      {choices.length > 0 && (
        <>
          <h4 className="system-section">{U.choose}</h4>
          <ul className="system-list">
            {choices.map((setting) => (
              <li key={setting.id} className="system-row">
                <span className="system-row-name" id={`${preferId}-${setting.id}`}>
                  {setting.title}
                </span>
                <select className="select" aria-labelledby={`${preferId}-${setting.id}`} value={String(setting.value ?? '')} onChange={(event) => void change(setting, event.target.value)}>
                  {setting.choices?.map((choice) => (
                    // A choice looser than the admin has it is shown, and is not theirs to take.
                    <option key={choice.value} value={choice.value} disabled={choice.disabled}>
                      {choice.disabled ? U.notYours(choice.label) : choice.label}
                    </option>
                  ))}
                </select>
              </li>
            ))}
          </ul>
        </>
      )}

      {others.length > 0 && (
        <>
          <h4 className="system-section">{U.chosen}</h4>
          <dl className="system-facts">
            {others.map((setting) => (
              <div key={setting.id} className="system-fact">
                <dt>{setting.title}</dt>
                <dd>{chosen(setting)}</dd>
              </div>
            ))}
          </dl>
        </>
      )}
      <div className="system-actions">
        <Button icon="settings" onClick={() => setSettingsOpen(true)}>
          {U.change}
        </Button>
      </div>

      {fixed.length > 0 && (
        <>
          <h4 className="system-section">{U.fixed}</h4>
          <dl className="system-facts">
            {fixed.map((setting) => (
              <div key={setting.id} className="system-fact">
                <dt>{setting.title}</dt>
                <dd>{chosen(setting)}</dd>
              </div>
            ))}
          </dl>
        </>
      )}

      {system.log && (
        <>
          <h4 className="system-section">{W.systems.log}</h4>
          <div className="system-actions">
            <Button onClick={async () => setLog(log ? null : await api.log(system.id))}>{log ? W.systems.logHide : W.systems.logShow}</Button>
          </div>
          {log && <LogLines log={log} />}
        </>
      )}

      {settingsOpen && (
        <SettingsScreen
          source={source}
          surface={surface}
          version={0}
          onClose={() => {
            setSettingsOpen(false);
            void source.load(surface).then(setAnswer, () => undefined);
          }}
          onChanged={setAnswer}
          onToast={onToast}
        />
      )}
    </article>
  );
}
