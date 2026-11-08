import { useEffect, useRef, useState } from 'react';

import { SettingRow, type RowStatus } from '../components/SettingsScreen';
import { Confirm } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { ChangeResult, RefusalReason, Setting, SettingsAnswer, SettingsSource, SettingValue } from '../settings/types';
import { W } from '../wording';

interface Props {
  source: SettingsSource;
  surface: Surface;
  version: number;
  skip?: readonly string[];
  lockedWords: string;
  refused: Record<RefusalReason, string>;
  noteFor?(setting: Setting): string | undefined;
  onChanged?(answer: SettingsAnswer): void;
  onToast(text: string): void;
}

export function SettingsList({ source, surface, version, skip, lockedWords, refused, noteFor, onChanged, onToast }: Props) {
  const [answer, setAnswer] = useState<SettingsAnswer | null>(null);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState<RowStatus | null>(null);
  const [asking, setAsking] = useState<Setting | null>(null);
  const changes = useRef(0);

  useEffect(() => {
    let current = true;
    const asked = changes.current;
    source.load(surface).then(
      (loaded) => {
        if (!current || asked !== changes.current) return;
        setAnswer(loaded);
        setFailed(false);
      },
      () => current && setFailed(true),
    );
    return () => {
      current = false;
    };
  }, [source, surface, version]);

  async function save(setting: Setting, value: SettingValue): Promise<boolean> {
    let result: ChangeResult;
    changes.current += 1;
    setStatus({ id: setting.id, tone: 'saving', text: W.settings.saving });
    try {
      result = await source.change(surface, { [setting.id]: value });
    } catch {
      setStatus({ id: setting.id, tone: 'refused', text: W.settings.notSaved });
      return false;
    } finally {
      changes.current += 1;
    }
    if (result.ok) {
      setAnswer(result.answer);
      onChanged?.(result.answer);
      setStatus({ id: setting.id, tone: 'saved', text: setting.applies === 'next_session' ? W.settings.savedNext : W.settings.saved });
    } else {
      setStatus({ id: setting.id, tone: 'refused', text: refused[result.reason] });
    }
    return result.ok;
  }

  async function run(setting: Setting) {
    setAsking(null);
    try {
      await source.run(surface, setting.id);
    } catch {
      setStatus({ id: setting.id, tone: 'refused', text: W.settings.clear.failed });
      return;
    }
    if (setting.id === 'clear_browsing_data') onToast(W.settings.clear.done);
  }

  if (!answer) {
    return (
      <p className="system-note" role="status">
        {failed ? W.systems.unreachable : W.settings.loading}
      </p>
    );
  }

  const groups = answer.groups.map((group) => ({ ...group, settings: group.settings.filter((setting) => !skip?.includes(setting.id)) })).filter((group) => group.settings.length > 0);
  return (
    <>
      {groups.map((group) => (
        <div key={group.id} className="system-group">
          <h4 className="system-section">{group.title}</h4>
          {group.settings.map((setting) => (
            <SettingRow
              key={setting.id}
              setting={setting}
              status={status?.id === setting.id ? status : null}
              source={source}
              onSave={(value) => save(setting, value)}
              onAct={() => (setting.confirm ? setAsking(setting) : void run(setting))}
              onToast={onToast}
              lockedWords={lockedWords}
              note={noteFor?.(setting)}
              lockedAsWords
            />
          ))}
        </div>
      ))}
      {asking?.confirm && (
        <Confirm
          question={asking.confirm.question}
          consequence={asking.confirm.consequence}
          confirm={asking.confirm.button}
          cancel={W.buttons.cancel}
          onConfirm={() => void run(asking)}
          onCancel={() => setAsking(null)}
        />
      )}
    </>
  );
}
