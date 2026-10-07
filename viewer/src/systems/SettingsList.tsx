// Every setting of one browser on the page itself (spec 9.17): each with a line saying what it
// does, and a control that works. These are the rows of the settings screen, with no screen to open:
// a setting is in one place.

import { useEffect, useRef, useState } from 'react';

import { SettingRow, type RowStatus } from '../components/SettingsScreen';
import { Confirm } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { ChangeResult, RefusalReason, Setting, SettingsAnswer, SettingsSource, SettingValue } from '../settings/types';
import { W } from '../wording';

interface Props {
  source: SettingsSource;
  surface: Surface;
  /** Goes up when the settings may have changed elsewhere, so that they are read again. */
  version: number;
  /** Settings drawn elsewhere on the card. */
  skip?: readonly string[];
  /** Who holds a setting that cannot be changed here. */
  lockedWords: string;
  /** Why a change was not taken, in the words for whoever is looking. */
  refused: Record<RefusalReason, string>;
  /** A line under a setting's description: who else the setting reaches. */
  noteFor?(setting: Setting): string | undefined;
  /** Told what the settings are after a change that was saved. */
  onChanged?(answer: SettingsAnswer): void;
  onToast(text: string): void;
}

export function SettingsList({ source, surface, version, skip, lockedWords, refused, noteFor, onChanged, onToast }: Props) {
  const [answer, setAnswer] = useState<SettingsAnswer | null>(null);
  const [failed, setFailed] = useState(false);
  const [status, setStatus] = useState<RowStatus | null>(null);
  const [asking, setAsking] = useState<Setting | null>(null);
  /** Goes up when a change begins and when it ends. What was read across one is older than the change. */
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
    // The service saves it. Until it has answered, the row says so and does not say Saved.
    setStatus({ id: setting.id, tone: 'saving', text: W.settings.saving });
    try {
      result = await source.change(surface, { [setting.id]: value });
    } catch {
      // The service did not answer. Nobody may believe the change was saved.
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
      // Nobody may believe the data is gone when it is not.
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
        // A heading, and not a landmark: "Browser" is also what the live browser itself is called.
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
