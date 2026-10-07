// The three browsers as systems (spec 9.17, 12.6). Each thing is in one place:
//  - under a browser's own tab, that browser alone: the admin's configuration of it or a user's own
//    settings for it, and what its tasks took;
//  - on the Systems page, for the admin, what is not one browser's: what users are allowed, and the
//    three compared.
// Everything here is drawn from what the service answers.

import { useCallback, useEffect, useState, type ReactNode } from 'react';

import type { Role } from '../auth/api';
import { Icon } from '../components/Icon';
import { Button } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { Setting, SettingsAnswer } from '../settings/types';
import { W } from '../wording';
import { Access, BrowsersCard, OverallCard, type Passwords } from './Access';
import type { Check, Evals, LogAnswer, Me, Overall, Policy, PolicyChange, SystemAction, SystemInfo, SystemsApi, TaskRow, TaskTrace } from './api';
import { clock, count, dollars, percent, spanOf } from './format';
import { CardHead, LogLines, NOT_RUNNING, SwitchRow, TableScroll } from './parts';
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

  const loadOverall = useCallback(() => void api.overall().then((told) => told && setOverall(told)), [api]);
  useEffect(() => {
    if (view !== 'overview') return;
    let current = true;
    void api.overall().then((told) => current && told && setOverall(told));
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
            <button key={name} type="button" role="tab" className="systems-view" aria-selected={view === name} onClick={() => setView(name)}>
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

/** One line of what a system's tasks took, with what the line is. */
function Fact({ name, hint, children }: { name: string; hint: string; children: ReactNode }) {
  return (
    <div className="system-fact">
      <dt>
        <span>{name}</span>
        <span className="system-row-hint">{hint}</span>
      </dt>
      <dd>{children}</dd>
    </div>
  );
}

function Evaluation({ system, api, word, sees }: { system: SystemInfo; api: SystemsApi; word: string; sees?: Me['sees'] }) {
  const [evals, setEvals] = useState<Evals | null>(null);
  const [failed, setFailed] = useState(false);
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState('');
  const [trace, setTrace] = useState<TaskTrace | null>(null);
  // What the admin lets this person see. When that changes, what is shown is asked for again.
  const seen = sees ? Object.values(sees).join() : '';

  const show = useCallback((told: Evals | null) => {
    setFailed(told === null);
    if (told) setEvals(told);
  }, []);
  const load = useCallback(async () => show(await api.evals(system.id)), [api, show, system.id]);

  useEffect(() => {
    let current = true;
    void api.evals(system.id).then((told) => current && show(told));
    return () => {
      current = false;
    };
  }, [api, show, system.id, seen]);

  async function run() {
    setNote('');
    setChecking(true);
    const done = await api.check(system.id);
    setChecking(false);
    if (!done.ok) setNote(done.why);
    await load();
  }

  async function rate(task: TaskRow, rating: 'good' | 'bad') {
    // Pressed again, a person takes their word back.
    await api.rate(system.id, task.id, task.rating === rating ? null : rating);
    await load();
  }

  async function showTrace(task: TaskRow) {
    setTrace(trace?.id === task.id ? null : await api.trace(system.id, task.id));
  }

  const name = W.backend[system.backend];
  const E = W.systems.evals;
  // What this person may be shown. The admin is shown all of it.
  const may = evals?.may ?? { cost: true, traces: true, checklist: true };
  return (
    <article className="system-card" aria-label={name}>
      <CardHead system={system} word={word} />
      <div className="system-actions">
        <Button hint={W.systems.refreshHint} onClick={() => void load()}>
          {W.systems.refresh}
        </Button>
      </div>
      {evals === null ? (
        <p className="system-note" role="status">
          {failed ? W.systems.unreachable : W.systems.loading}
        </p>
      ) : (
        <>
          <dl className="system-facts">
            <Fact name={E.model} hint={E.hint.model}>
              {evals.model}
            </Fact>
            <Fact name={E.tasks} hint={E.hint.tasks}>
              {evals.tasks.count === 0 ? (
                E.none
              ) : (
                <>
                  <span>{E.tasksLine(evals.tasks.count, evals.tasks.steps)}</span>
                  <span>{E.ended(evals.tasks.failed, evals.tasks.stopped, evals.tasks.step_limit)}</span>
                </>
              )}
            </Fact>
            {evals.tasks.count > 0 && (
              <>
                <Fact name={E.quality} hint={E.hint.quality}>
                  <span>{E.answered(percent(evals.tasks.success_rate), evals.tasks.answered, evals.tasks.count)}</span>
                  <span>{E.stepsFailed(evals.tasks.steps_failed, evals.tasks.steps)}</span>
                  <span>{E.rated(evals.tasks.rated_good, evals.tasks.rated_bad)}</span>
                </Fact>
                <Fact name={E.latency} hint={E.hint.latency}>
                  <span>{E.step(spanOf(evals.latency.tool.p50_ms), spanOf(evals.latency.tool.p95_ms))}</span>
                  <span>{E.reply(spanOf(evals.latency.model.p50_ms), spanOf(evals.latency.model.p95_ms))}</span>
                </Fact>
                <Fact name={E.time} hint={E.hint.time}>
                  <span>{E.task(spanOf(evals.time.task.p50_ms), spanOf(evals.time.task.p95_ms))}</span>
                  <span>{E.shares(percent(evals.time.model_share), percent(evals.time.tool_share), percent(evals.time.waiting_share))}</span>
                </Fact>
                {evals.cost && (
                  <Fact name={E.cost} hint={E.hint.cost}>
                    {evals.cost.tasks_counted === 0 ? (
                      E.noTokens
                    ) : (
                      <>
                        <span>{E.tokens(count(evals.cost.input_tokens), count(evals.cost.output_tokens))}</span>
                        <span>{evals.cost.usd === null ? E.noPrice : E.dollars(dollars(evals.cost.usd), dollars(evals.cost.usd_per_task ?? 0))}</span>
                      </>
                    )}
                  </Fact>
                )}
              </>
            )}
          </dl>

          {evals.latency.by_tool.length > 0 && (
            <>
              <h4 className="system-section">{E.performance}</h4>
              <p className="system-hint">{E.performanceLead}</p>
              <TableScroll label={E.performance}>
              <table className="system-table">
                <thead>
                  <tr>
                    <th scope="col">{E.tool}</th>
                    <th scope="col">{E.calls}</th>
                    <th scope="col">{E.typical}</th>
                    <th scope="col">{E.slow}</th>
                    <th scope="col">{E.failures}</th>
                  </tr>
                </thead>
                <tbody>
                  {evals.latency.by_tool.map((row) => (
                    <tr key={row.tool}>
                      <th scope="row">{row.tool.replace('browser_', '')}</th>
                      <td>{row.count}</td>
                      <td>{spanOf(row.p50_ms)}</td>
                      <td>{spanOf(row.p95_ms)}</td>
                      <td>{row.failed}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </TableScroll>
            </>
          )}

          {may.checklist && (
            <>
              <h4 className="system-section">{E.checklist}</h4>
              <p className="system-hint">{E.checklistLead}</p>
              <div className="system-actions">
                <Button kind="primary" icon="check" busy={checking || evals.checking} onClick={() => void run()}>
                  {checking || evals.checking ? E.running : E.run}
                </Button>
              </div>
              {note && (
                <p className="system-note" role="status">
                  {note}
                </p>
              )}
              {evals.checklist ? (
                <>
                  <p className="system-note" data-tone={evals.checklist.failed ? 'danger' : 'success'}>
                    {E.passed(evals.checklist.passed, evals.checklist.checks.length)}. {E.ran(clock(evals.checklist.ran), spanOf(evals.checklist.duration_ms))}
                  </p>
                  <ul className="system-checks">
                    {evals.checklist.checks.map((check) => (
                      <CheckLine key={check.id} check={check} />
                    ))}
                  </ul>
                </>
              ) : (
                <p className="system-note">{E.neverRun}</p>
              )}
            </>
          )}

          {may.traces && evals.recent.length > 0 && (
            <>
              <h4 className="system-section">{E.traces}</h4>
              <p className="system-hint">{E.tracesLead}</p>
              <ul className="system-tasks">
                {evals.recent.map((task) => (
                  <li key={task.id} className="system-task" data-outcome={task.outcome}>
                    <p className="system-task-words">{task.task || E.noWords}</p>
                    <p className="system-note">
                      {E.outcome[task.outcome]}. {E.facts(spanOf(task.duration_ms), task.steps, task.model_calls)}
                      {task.cost_usd !== null && `, ${dollars(task.cost_usd)}`}
                    </p>
                    <div className="system-actions">
                      {/* The one a person chose is the solid one. Pressed again, it is taken back. */}
                      <Button icon="check" kind={task.rating === 'good' ? 'primary' : 'plain'} hint={E.goodHint} onClick={() => void rate(task, 'good')}>
                        {E.good}
                      </Button>
                      <Button icon="close" kind={task.rating === 'bad' ? 'primary' : 'plain'} hint={E.badHint} onClick={() => void rate(task, 'bad')}>
                        {E.bad}
                      </Button>
                      <Button hint={E.traceHint} onClick={() => void showTrace(task)}>
                        {trace?.id === task.id ? E.hideTrace : E.showTrace}
                      </Button>
                    </div>
                    {trace?.id === task.id && <Trace trace={trace} />}
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </article>
  );
}

function CheckLine({ check }: { check: Check }) {
  const E = W.systems.evals;
  return (
    <li className="system-check" data-state={check.state}>
      <Icon name={check.state === 'ok' ? 'check' : check.state === 'failed' ? 'alert' : 'pause'} />
      <span className="system-check-title">
        <span className="sr-only">{E.state[check.state]}: </span>
        {check.title}
        {check.detail && <span className="system-check-detail">{check.detail}</span>}
      </span>
      {check.ms !== null && <span className="system-check-took">{spanOf(check.ms)}</span>}
    </li>
  );
}

/** Every reply of the model and every step of one task, each as a bar where and as long as it was. */
function Trace({ trace }: { trace: TaskTrace }) {
  const E = W.systems.evals;
  const whole = Math.max(trace.duration_ms, 1);
  return (
    <ol className="system-trace" aria-label={E.trace}>
      {trace.spans.map((span, index) => (
        <li key={index} className="system-span" data-kind={span.kind} data-ok={span.ok}>
          <span className="system-span-name">{span.kind === 'model' ? E.theModel : span.name.replace('browser_', '')}</span>
          <span className="system-span-track" aria-hidden="true">
            <span className="system-span-bar" style={{ marginInlineStart: `${Math.min((span.at_ms / whole) * 100, 99)}%`, width: `${Math.max((span.ms / whole) * 100, 1)}%` }} />
          </span>
          <span className="system-span-took">
            {spanOf(span.ms)}
            {span.waited_ms > 0 && <span className="system-check-detail">{E.waited(spanOf(span.waited_ms))}</span>}
            {span.kind === 'model' && span.input_tokens > 0 && <span className="system-check-detail">{E.spanTokens(count(span.input_tokens), count(span.output_tokens))}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
