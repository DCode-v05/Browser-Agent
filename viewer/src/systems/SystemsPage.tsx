// The three browsers as systems (spec 9.17, 12.6). Each thing is in one place:
//  - under a browser's own tab, that browser alone: the admin's configuration of it or a user's own
//    settings for it, and what its tasks took;
//  - on the Systems page, for the admin, what is not one browser's: what users are allowed, and the
//    three compared.
// Everything here is drawn from what the service answers.

import { useCallback, useEffect, useState } from 'react';

import type { Role } from '../auth/api';
import { Button } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { Setting, SettingsAnswer } from '../settings/types';
import { W } from '../wording';
import { Access, BrowsersCard, OverallCard, type Passwords } from './Access';
import type { LogAnswer, Me, Overall, Policy, PolicyChange, SuiteOverall, SystemAction, SystemInfo, SystemsApi } from './api';
import { Evaluation } from './Evaluation';
import { ParityCard } from './Suite';
import { CardHead, LogLines, NOT_RUNNING, SwitchRow } from './parts';
import { SettingsList } from './SettingsList';
import { UserSettings } from './UserSettings';

/** What the Systems page shows: what users are allowed, or the three browsers compared. */
type View = 'users' | 'overview';
/** Under a browser's own tab a user has their settings where the admin has the configuration. */
export type PanelView = 'configuration' | 'evaluations' | 'settings';
/** "Use this browser" has a row of its own at the top of the card. */
const OWN_ROW = ['system_enabled'];

interface Props {
  api: SystemsApi;
  /** How often the service is asked where the systems stand, in milliseconds. 0 asks once. */
  pollMs: number;
  /** The word for where a system stands, as its tab says it. */
  wordFor(system: SystemInfo): string;
}

/** Where the systems stand, asked of the service now and at a steady pace after that. */
function useSystems(api: SystemsApi, pollMs: number) {
  const [systems, setSystems] = useState<SystemInfo[] | null>(null);
  const [failed, setFailed] = useState(false);
  /** Goes up each time the service has answered: what else is drawn from it is read again then. */
  const [asked, setAsked] = useState(0);

  const show = useCallback((listed: SystemInfo[] | null) => {
    setFailed(listed === null);
    // An answer that could not be had changes nothing: what was known stays on screen.
    if (!listed) return;
    setSystems(listed);
    setAsked((times) => times + 1);
  }, []);
  const load = useCallback(async () => show(await api.list()), [api, show]);

  useEffect(() => {
    let current = true;
    const ask = () => void api.list().then((listed) => current && show(listed));
    ask();
    const timer = pollMs ? setInterval(ask, pollMs) : undefined;
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [api, pollMs, show]);

  return { systems, failed, load, asked };
}

/** What the admin lets users use, change and see: read once, and changed a line at a time. */
function usePolicy(api: SystemsApi, role: Role) {
  const [policy, setPolicy] = useState<Policy | null>(null);
  useEffect(() => {
    if (role !== 'admin') return;
    let current = true;
    void api.policy().then((told) => current && told && setPolicy(told));
    return () => {
      current = false;
    };
  }, [api, role]);
  const change = useCallback(
    async (changes: PolicyChange) => {
      const told = await api.changePolicy(changes);
      if (told) setPolicy(told);
    },
    [api],
  );
  return { policy, change };
}

interface PanelProps extends Props {
  surface: Surface;
  /** The one system to show. */
  system: string;
  view: PanelView;
  /** Who is looking: the admin has the configuration, a user their own settings. */
  role: Role;
  me?: Me | null;
  /** The person chose the browser their window opens on. */
  onPrefer?(system: string): void;
  /** Told when the system was changed here, so that its tab follows at once. */
  onChanged?(): void;
  /** Told what the settings are after one was changed here: the colour mode holds for the whole window. */
  onSettings?(answer: SettingsAnswer): void;
}

/** One system by itself, under its own tab of the window: how it is set up, or what its tasks took. */
export function SystemPanel({ api, system: id, view, role, me, onPrefer, surface, pollMs, wordFor, onChanged, onSettings }: PanelProps) {
  const { systems, failed, load, asked } = useSystems(api, pollMs);
  const { policy, change: changePolicy } = usePolicy(api, role);
  const [said, setSaid] = useState('');
  const system = systems?.find((one) => one.id === id);
  const changed = useCallback(async () => {
    await load();
    onChanged?.();
  }, [load, onChanged]);
  const P = W.systems.panel;

  return (
    <section className="systems" data-single="true" aria-label={view === 'settings' ? W.systems.user.title : W.systems[view]}>
      {system && (
        // Whose page this is and what it is for, said before anything is changed on it.
        <header className="systems-head">
          <div>
            <h2 className="systems-title">{P.title[view](W.backend[system.backend])}</h2>
            <p className="systems-lead">{view === 'evaluations' ? P.lead.evaluations[role] : P.lead[view]}</p>
          </div>
        </header>
      )}
      {said && (
        <p className="systems-note" role="status">
          {said}
        </p>
      )}
      {!system ? (
        <p className="systems-note" role="status">
          {failed ? W.systems.unreachable : W.systems.loading}
        </p>
      ) : (
        <div className="systems-grid" data-single="true">
          {view === 'evaluations' ? (
            <Evaluation system={system} api={api} word={wordFor(system)} sees={me?.sees} />
          ) : role === 'admin' ? (
            <Configuration
              system={system}
              api={api}
              surface={surface}
              word={wordFor(system)}
              version={asked}
              onChanged={changed}
              onSettings={onSettings}
              onToast={setSaid}
              policy={policy}
              onPolicy={(changes) => void changePolicy(changes).then(changed)}
            />
          ) : (
            me && (
              <UserSettings
                system={system}
                systems={systems ?? []}
                api={api}
                surface={surface}
                word={wordFor(system)}
                me={me}
                version={asked}
                onPrefer={(chosenOne) => onPrefer?.(chosenOne)}
                onSettings={onSettings}
                onToast={setSaid}
              />
            )
          )}
        </div>
      )}
    </section>
  );
}

interface PageProps extends Props {
  /** For the admin: sets the two passwords. */
  passwords?: Passwords;
  /** Goes to a browser's own tab, on its configuration or its evaluations. */
  onOpen(system: string, view: 'configuration' | 'evaluations'): void;
}

/** The admin's page of what is not one browser's: what users are allowed, and the three compared. */
export function SystemsPage({ api, pollMs, wordFor, passwords, onOpen }: PageProps) {
  const [view, setView] = useState<View>('users');
  const { systems, failed } = useSystems(api, pollMs);
  const { policy, change: changePolicy } = usePolicy(api, 'admin');
  const [overall, setOverall] = useState<Overall | null>(null);

  const [parity, setParity] = useState<SuiteOverall | null>(null);
  const loadOverall = useCallback(() => void api.overall().then((told) => told && setOverall(told)), [api]);
  const loadParity = useCallback(() => void api.suiteOverall().then((told) => told && setParity(told)), [api]);
  useEffect(() => {
    if (view !== 'overview') return;
    let current = true;
    void api.overall().then((told) => current && told && setOverall(told));
    void api.suiteOverall().then((told) => current && told && setParity(told));
    return () => {
      current = false;
    };
  }, [api, view]);
  const nameOf = (id: string) => {
    const system = systems?.find((one) => one.id === id);
    return system ? W.backend[system.backend] : id;
  };

  return (
    <section className="systems" aria-label={W.systems.title}>
      <header className="systems-head">
        <div>
          <h2 className="systems-title">{W.systems.title}</h2>
          <p className="systems-lead">{W.systems.lead}</p>
        </div>
        <div className="systems-views" role="tablist" aria-label={W.systems.views}>
          {(['users', 'overview'] as const).map((name) => (
            <button key={name} type="button" role="tab" className="systems-view" aria-selected={view === name} title={W.systems.viewHint[name]} onClick={() => setView(name)}>
              {W.systems.view[name]}
            </button>
          ))}
        </div>
      </header>
      {systems === null ? (
        <p className="systems-note" role="status">
          {failed ? W.systems.unreachable : W.systems.loading}
        </p>
      ) : view === 'users' ? (
        policy && <Access policy={policy} systems={systems} onPolicy={(changes) => void changePolicy(changes)} passwords={passwords} onOpen={(id) => onOpen(id, 'configuration')} />
      ) : (
        <>
          <BrowsersCard systems={systems} policy={policy} wordFor={wordFor} onOpen={onOpen} />
          <OverallCard overall={overall} nameOf={nameOf} onRefresh={loadOverall} />
          <ParityCard overall={parity} nameOf={nameOf} onRefresh={loadParity} />
        </>
      )}
    </section>
  );
}

interface ConfigurationProps {
  system: SystemInfo;
  api: SystemsApi;
  surface: Surface;
  word: string;
  /** Goes up when the service has been asked again: the settings are read again with it. */
  version: number;
  onChanged(): Promise<void>;
  onSettings?(answer: SettingsAnswer): void;
  onToast(text: string): void;
  /** What the admin lets users use and change. Null until the service has said. */
  policy: Policy | null;
  onPolicy(changes: PolicyChange): void;
}

/** The admin's configuration of one system: whether it runs, whether users may use it, and every
 *  setting it has, each with what it does and a control that works. */
function Configuration({ system, api, surface, word, version, onChanged, onSettings, onToast, policy, onPolicy }: ConfigurationProps) {
  const source = api.settings(system.id);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<SystemAction | null>(null);
  const [log, setLog] = useState<LogAnswer | null>(null);

  async function turn(on: boolean) {
    setNote('');
    try {
      const result = await source.change(surface, { system_enabled: on });
      if (!result.ok) setNote(W.settings.refused[result.reason]);
    } catch {
      setNote(W.settings.notSaved);
    }
    await onChanged();
  }

  async function manage(action: SystemAction) {
    setNote('');
    setBusy(action);
    const done = await api.manage(system.id, action);
    setBusy(null);
    if (!done.ok) setNote(done.why);
    await onChanged();
  }

  /** Who else a setting reaches: every browser, and the users. */
  function noteFor(setting: Setting): string | undefined {
    const line = policy?.may_change.find((one) => one.id === setting.id);
    const said = [setting.scope === 'all' ? W.systems.everyBrowser : '', line ? (line.allowed ? W.systems.usersMay : W.systems.usersHeld) : ''];
    return said.filter(Boolean).join(' ') || undefined;
  }

  const running = !NOT_RUNNING.has(system.state);
  const forUsers = policy?.systems.find((line) => line.id === system.id);
  // A person's own Chrome is not started from here: its session begins when its extension dials in.
  const waitsForChrome = system.backend === 'takeover_chrome' && system.state === 'waiting';
  const name = W.backend[system.backend];
  const A = W.systems.access;
  return (
    <article className="system-card" aria-label={name} data-enabled={system.enabled}>
      <CardHead system={system} word={word} />

      <h4 className="system-section">{W.systems.thisBrowser}</h4>
      <SwitchRow title={W.systems.use} description={W.systems.useLead} label={`${W.systems.use}: ${name}`} on={system.enabled} onChange={(next) => void turn(next)} />
      <div className="system-actions">
        {running ? (
          <>
            <Button icon="play" busy={busy === 'restart'} disabled={!system.enabled} hint={W.systems.restartHint} onClick={() => void manage('restart')}>
              {W.systems.restart}
            </Button>
            <Button icon="stop" busy={busy === 'stop'} disabled={!system.enabled} hint={W.systems.stopHint} onClick={() => void manage('stop')}>
              {W.systems.stop}
            </Button>
          </>
        ) : (
          !waitsForChrome && (
            <Button icon="play" kind="primary" busy={busy === 'start'} disabled={!system.enabled} hint={W.systems.startHint} onClick={() => void manage('start')}>
              {W.systems.start}
            </Button>
          )
        )}
      </div>
      {!waitsForChrome && <p className="system-hint">{W.systems.manageLead[!system.enabled ? 'off' : running ? 'running' : 'stopped']}</p>}
      {(note || system.note || waitsForChrome) && (
        <p className="system-note" role="status">
          {note || system.note || W.systems.chromeWaits}
        </p>
      )}

      {forUsers && (
        <>
          <h4 className="system-section">{W.systems.forUsers}</h4>
          <SwitchRow title={A.users} description={A.usersLead} label={`${A.users}: ${name}`} on={forUsers.allowed} onChange={(next) => onPolicy({ systems: { [system.id]: next } })} />
          <p className="system-hint">{W.systems.forUsersLead}</p>
        </>
      )}

      <SettingsList
        source={source}
        surface={surface}
        version={version}
        skip={OWN_ROW}
        lockedWords={W.systems.locked}
        refused={W.settings.refused}
        noteFor={noteFor}
        // A change may be to what the card itself shows: the log that was turned off, the model.
        onChanged={(answer) => {
          onSettings?.(answer);
          void onChanged();
        }}
        onToast={onToast}
      />

      <h4 className="system-section">{W.systems.log}</h4>
      <p className="system-hint">{W.systems.logLead}</p>
      {system.log ? (
        <>
          <code className="system-path">{system.log}</code>
          <div className="system-actions">
            <Button hint={W.systems.logHint} onClick={async () => setLog(log ? null : await api.log(system.id))}>
              {log ? W.systems.logHide : W.systems.logShow}
            </Button>
          </div>
          {log && <LogLines log={log} />}
        </>
      ) : (
        <p className="system-note">{W.systems.logOff}</p>
      )}
      {system.records && (
        <>
          <h4 className="system-section">{W.systems.records}</h4>
          <p className="system-hint">{W.systems.recordsLead}</p>
          <code className="system-path">{system.records}</code>
        </>
      )}
    </article>
  );
}
