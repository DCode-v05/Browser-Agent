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
import { useWords } from '../words';

type View = 'users' | 'overview';
export type PanelView = 'configuration' | 'evaluations' | 'settings';
const OWN_ROW = ['system_enabled'];

interface Props {
  api: SystemsApi;
  pollMs: number;
  wordFor(system: SystemInfo): string;
}

function useSystems(api: SystemsApi, pollMs: number) {
  const [systems, setSystems] = useState<SystemInfo[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [asked, setAsked] = useState(0);

  const show = useCallback((listed: SystemInfo[] | null) => {
    setFailed(listed === null);
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
  system: string;
  view: PanelView;
  role: Role;
  me?: Me | null;
  onPrefer?(system: string): void;
  onChanged?(): void;
  onSettings?(answer: SettingsAnswer): void;
}

export function SystemPanel({ api, system: id, view, role, me, onPrefer, surface, pollMs, wordFor, onChanged, onSettings }: PanelProps) {
  const L = useWords();
  const { systems, failed, load, asked } = useSystems(api, pollMs);
  const { policy, change: changePolicy } = usePolicy(api, role);
  const [said, setSaid] = useState('');
  const system = systems?.find((one) => one.id === id);
  const changed = useCallback(async () => {
    await load();
    onChanged?.();
  }, [load, onChanged]);
  const P = L.systems.panel;

  return (
    <section className="systems" data-single="true" aria-label={view === 'settings' ? W.systems.user.title : W.systems[view]}>
      {system && (
        <header className="systems-head">
          <div>
            <h2 className="systems-title">{P.title[view](W.backend[system.backend])}</h2>
            <p className="systems-lead">{view === 'evaluations' ? P.lead.evaluations[role] : view === 'configuration' && system.backend === 'contained_desktop' ? W.systems.desktop.configuration : P.lead[view]}</p>
          </div>
        </header>
      )}
      {said && (
        <p className="systems-note" role="status">
          {said}
        </p>
      )}
      {!system ? (
        <div className="systems-empty">
          <p className="systems-note" role="status">
            {failed ? W.systems.unreachable : W.systems.loading}
          </p>
        </div>
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
  passwords?: Passwords;
  onOpen(system: string, view: 'configuration' | 'evaluations'): void;
}

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
        <div className="systems-empty">
          <p className="systems-note" role="status">
            {failed ? W.systems.unreachable : W.systems.loading}
          </p>
        </div>
      ) : view === 'users' ? (
        policy ? (
          <Access policy={policy} systems={systems} onPolicy={(changes) => void changePolicy(changes)} passwords={passwords} onOpen={(id) => onOpen(id, 'configuration')} />
        ) : (
          <div className="systems-empty">
            <p className="systems-note" role="status">
              {W.systems.loading}
            </p>
          </div>
        )
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
  version: number;
  onChanged(): Promise<void>;
  onSettings?(answer: SettingsAnswer): void;
  onToast(text: string): void;
  policy: Policy | null;
  onPolicy(changes: PolicyChange): void;
}

function Configuration({ system, api, surface, word, version, onChanged, onSettings, onToast, policy, onPolicy }: ConfigurationProps) {
  const L = useWords();
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

  function noteFor(setting: Setting): string | undefined {
    const line = policy?.may_change.find((one) => one.id === setting.id);
    const said = [setting.scope === 'all' ? W.systems.everyBrowser : '', line ? (line.allowed ? W.systems.usersMay : W.systems.usersHeld) : ''];
    return said.filter(Boolean).join(' ') || undefined;
  }

  const running = !NOT_RUNNING.has(system.state);
  const forUsers = policy?.systems.find((line) => line.id === system.id);
  const waitsForChrome = system.backend === 'takeover_chrome' && system.state === 'waiting';
  const name = W.backend[system.backend];
  const S = system.backend === 'contained_desktop' ? { ...W.systems, ...W.systems.desktop } : W.systems;
  const A = system.backend === 'contained_desktop' ? { ...W.systems.access, ...W.systems.desktop } : W.systems.access;
  return (
    <article className="system-card" aria-label={name} data-enabled={system.enabled}>
      <CardHead system={system} word={word} />

      <h4 className="system-section">{S.thisBrowser}</h4>
      <SwitchRow title={S.use} description={S.useLead} label={`${S.use}: ${name}`} on={system.enabled} onChange={(next) => void turn(next)} />
      <div className="system-actions">
        {running ? (
          <>
            <Button icon="play" busy={busy === 'restart'} disabled={!system.enabled} hint={S.restartHint} onClick={() => void manage('restart')}>
              {W.systems.restart}
            </Button>
            <Button icon="stop" busy={busy === 'stop'} disabled={!system.enabled} hint={S.stopHint} onClick={() => void manage('stop')}>
              {W.systems.stop}
            </Button>
          </>
        ) : (
          !waitsForChrome && (
            <Button icon="play" kind="primary" busy={busy === 'start'} disabled={!system.enabled} hint={S.startHint} onClick={() => void manage('start')}>
              {W.systems.start}
            </Button>
          )
        )}
      </div>
      {!waitsForChrome && <p className="system-hint">{S.manageLead[!system.enabled ? 'off' : running ? 'running' : 'stopped']}</p>}
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
        onChanged={(answer) => {
          onSettings?.(answer);
          void onChanged();
        }}
        onToast={onToast}
      />

      <h4 className="system-section">{W.systems.log}</h4>
      <p className="system-hint">{L.systems.logLead}</p>
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
        <p className="system-note">{L.systems.logOff}</p>
      )}
      {system.records && (
        <>
          <h4 className="system-section">{W.systems.records}</h4>
          <p className="system-hint">{L.systems.recordsLead}</p>
          <code className="system-path">{system.records}</code>
        </>
      )}
    </article>
  );
}
