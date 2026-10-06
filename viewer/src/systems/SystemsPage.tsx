// The three browsers as systems (spec 9.17, 12.6): for each, whether it is in use, what the agent may
// do in it, its log, and what its tasks took. Everything here is drawn from what the service answers.

import { useCallback, useEffect, useState } from 'react';

import type { Role } from '../auth/api';
import { Icon } from '../components/Icon';
import { SettingsScreen } from '../components/SettingsScreen';
import { Button } from '../components/StatusPanel';
import type { Surface } from '../protocol';
import type { SettingsAnswer } from '../settings/types';
import { W } from '../wording';
import { Access, OverallCard, type Passwords } from './Access';
import type { Check, Evals, LogAnswer, Me, Overall, Policy, PolicyChange, SystemAction, SystemInfo, SystemsApi, TaskRow, TaskTrace } from './api';
import { clock, count, dollars, percent, spanOf } from './format';
import { CardHead, chosen, LogLines, NOT_RUNNING, Switch } from './parts';
import { UserSettings } from './UserSettings';

type View = 'configuration' | 'evaluations';
/** Under a browser's own tab a user has their settings where the admin has the configuration. */
export type PanelView = View | 'settings';

interface Props {
  api: SystemsApi;
  surface: Surface;
  /** How often the service is asked where the systems stand, in milliseconds. 0 asks once. */
  pollMs: number;
  /** The word for where a system stands, as its tab says it. */
  wordFor(system: SystemInfo): string;
}

/** Where the systems stand, asked of the service now and at a steady pace after that. */
function useSystems(api: SystemsApi, pollMs: number) {
  const [systems, setSystems] = useState<SystemInfo[] | null>(null);
  const [failed, setFailed] = useState(false);

  const show = useCallback((listed: SystemInfo[] | null) => {
    setFailed(listed === null);
    // An answer that could not be had changes nothing: what was known stays on screen.
    if (listed) setSystems(listed);
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

  return { systems, failed, load };
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
}

/** One system by itself, under its own tab of the window: how it is set up, or what its tasks took. */
export function SystemPanel({ api, system: id, view, role, me, onPrefer, surface, pollMs, wordFor, onChanged }: PanelProps) {
  const { systems, failed, load } = useSystems(api, pollMs);
  const { policy, change: changePolicy } = usePolicy(api, role);
  const [said, setSaid] = useState('');
  const system = systems?.find((one) => one.id === id);
  const changed = useCallback(async () => {
    await load();
    onChanged?.();
  }, [load, onChanged]);

  return (
    <section className="systems" aria-label={view === 'settings' ? W.systems.user.title : W.systems[view]}>
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
            <Evaluation system={system} api={api} word={wordFor(system)} />
          ) : role === 'admin' ? (
            <Configuration system={system} api={api} surface={surface} word={wordFor(system)} onChanged={changed} onToast={setSaid} policy={policy} onPolicy={(changes) => void changePolicy(changes).then(changed)} />
          ) : (
            me && <UserSettings system={system} systems={systems ?? []} api={api} surface={surface} word={wordFor(system)} me={me} onPrefer={(chosenOne) => onPrefer?.(chosenOne)} onToast={setSaid} />
          )}
        </div>
      )}
    </section>
  );
}

/** The admin's page of the whole: the three systems side by side, what users are allowed, and all of it as one. */
export function SystemsPage({ api, surface, pollMs, wordFor, passwords }: Props & { passwords?: Passwords }) {
  const [view, setView] = useState<View>('configuration');
  const { systems, failed, load } = useSystems(api, pollMs);
  const { policy, change: changePolicy } = usePolicy(api, 'admin');
  const [overall, setOverall] = useState<Overall | null>(null);
  /** What a settings screen opened from here has to say, such as that data was cleared. */
  const [said, setSaid] = useState('');

  const loadOverall = useCallback(() => void api.overall().then((told) => told && setOverall(told)), [api]);
  useEffect(() => {
    if (view !== 'evaluations') return;
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
          {(['configuration', 'evaluations'] as const).map((name) => (
            <button key={name} type="button" role="tab" className="systems-view" aria-selected={view === name} onClick={() => setView(name)}>
              {W.systems[name]}
            </button>
          ))}
        </div>
      </header>
      {said && (
        <p className="systems-note" role="status">
          {said}
        </p>
      )}
      {systems === null ? (
        <p className="systems-note" role="status">
          {failed ? W.systems.unreachable : W.systems.loading}
        </p>
      ) : (
        <>
          {/* What is of every system comes first: the users' access, and the tasks of all as one. */}
          {view === 'configuration' && policy && <Access policy={policy} onPolicy={(changes) => void changePolicy(changes)} passwords={passwords} />}
          {view === 'evaluations' && <OverallCard overall={overall} nameOf={nameOf} onRefresh={loadOverall} />}
          <div className="systems-grid">
            {systems.map((system) =>
              view === 'configuration' ? (
                <Configuration key={system.id} system={system} api={api} surface={surface} word={wordFor(system)} onChanged={load} onToast={setSaid} policy={policy} onPolicy={(changes) => void changePolicy(changes)} />
              ) : (
                <Evaluation key={system.id} system={system} api={api} word={wordFor(system)} />
              ),
            )}
          </div>
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
  onChanged(): Promise<void>;
  onToast(text: string): void;
  /** What the admin lets users use. Null until the service has said. */
  policy: Policy | null;
  onPolicy(changes: PolicyChange): void;
}

/** The admin's card of one system: whether it runs, who may use it, and what the agent may do in it. */
function Configuration({ system, api, surface, word, onChanged, onToast, policy, onPolicy }: ConfigurationProps) {
  const source = api.settings(system.id);
  const [answer, setAnswer] = useState<SettingsAnswer | null>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<SystemAction | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [log, setLog] = useState<LogAnswer | null>(null);

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

  const own = (answer?.groups.flatMap((group) => group.settings) ?? []).filter((setting) => setting.scope === 'system' && setting.id !== 'system_enabled');
  const switches = own.filter((setting) => setting.control === 'switch');
  const others = own.filter((setting) => setting.control !== 'switch' && setting.control !== 'action' && setting.control !== 'about');

  async function change(id: string, value: boolean) {
    setNote('');
    try {
      const result = await source.change(surface, { [id]: value });
      if (result.ok) setAnswer(result.answer);
      else setNote(W.settings.refused[result.reason]);
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

  const running = !NOT_RUNNING.has(system.state);
  const forUsers = policy?.systems.find((line) => line.id === system.id);
  // A person's own Chrome is not started from here: its session begins when its extension dials in.
  const waitsForChrome = system.backend === 'takeover_chrome' && system.state === 'waiting';
  const name = W.backend[system.backend];
  return (
    <article className="system-card" aria-label={name} data-enabled={system.enabled}>
      <CardHead system={system} word={word} />
      <div className="system-row">
        <span className="system-row-name">{W.systems.use}</span>
        <Switch label={`${W.systems.use}: ${name}`} on={system.enabled} onChange={(next) => void change('system_enabled', next)} />
      </div>
      {forUsers && (
        <div className="system-row">
          <span className="system-row-name">
            {W.systems.access.users}
            <span className="system-locked">{W.systems.access.usersLead}</span>
          </span>
          <Switch label={`${W.systems.access.users}: ${name}`} on={forUsers.allowed} onChange={(next) => onPolicy({ systems: { [system.id]: next } })} />
        </div>
      )}
      <div className="system-actions">
        {running ? (
          <>
            <Button icon="play" busy={busy === 'restart'} disabled={!system.enabled} onClick={() => void manage('restart')}>
              {W.systems.restart}
            </Button>
            <Button icon="stop" busy={busy === 'stop'} disabled={!system.enabled} onClick={() => void manage('stop')}>
              {W.systems.stop}
            </Button>
          </>
        ) : (
          !waitsForChrome && (
            <Button icon="play" kind="primary" busy={busy === 'start'} disabled={!system.enabled} onClick={() => void manage('start')}>
              {W.systems.start}
            </Button>
          )
        )}
        <Button icon="settings" onClick={() => setSettingsOpen(true)}>
          {W.systems.allSettings}
        </Button>
      </div>
      {(note || system.note || waitsForChrome) && (
        <p className="system-note" role="status">
          {note || system.note || W.systems.chromeWaits}
        </p>
      )}

      <h4 className="system-section">{W.systems.may}</h4>
      <ul className="system-list">
        {switches.map((setting) => (
          <li key={setting.id} className="system-row">
            <span className="system-row-name">
              {setting.title}
              {setting.locked && <span className="system-locked">{W.systems.locked}</span>}
            </span>
            <Switch label={`${setting.title}: ${name}`} on={setting.value === true} locked={setting.locked} onChange={(next) => void change(setting.id, next)} />
          </li>
        ))}
      </ul>

      <h4 className="system-section">{W.systems.chosen}</h4>
      <dl className="system-facts">
        {others.map((setting) => (
          <div key={setting.id} className="system-fact">
            <dt>{setting.title}</dt>
            <dd>{chosen(setting)}</dd>
          </div>
        ))}
      </dl>

      <h4 className="system-section">{W.systems.log}</h4>
      {system.log ? (
        <>
          <code className="system-path">{system.log}</code>
          <div className="system-actions">
            <Button onClick={async () => setLog(log ? null : await api.log(system.id))}>{log ? W.systems.logHide : W.systems.logShow}</Button>
          </div>
          {log && <LogLines log={log} />}
        </>
      ) : (
        <p className="system-note">{W.systems.logOff}</p>
      )}
      {system.records && (
        <>
          <h4 className="system-section">{W.systems.records}</h4>
          <code className="system-path">{system.records}</code>
        </>
      )}

      {settingsOpen && (
        <SettingsScreen
          source={source}
          surface={surface}
          version={0}
          onClose={() => {
            setSettingsOpen(false);
            // What was changed in the screen shows on the card.
            void source.load(surface).then(setAnswer, () => undefined);
            void onChanged();
          }}
          onChanged={setAnswer}
          onToast={onToast}
        />
      )}
    </article>
  );
}

function Evaluation({ system, api, word }: { system: SystemInfo; api: SystemsApi; word: string }) {
  const [evals, setEvals] = useState<Evals | null>(null);
  const [failed, setFailed] = useState(false);
  const [checking, setChecking] = useState(false);
  const [note, setNote] = useState('');
  const [trace, setTrace] = useState<TaskTrace | null>(null);

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
  }, [api, show, system.id]);

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
        <Button onClick={() => void load()}>{W.systems.refresh}</Button>
      </div>
      {evals === null ? (
        <p className="system-note" role="status">
          {failed ? W.systems.unreachable : W.systems.loading}
        </p>
      ) : (
        <>
          <dl className="system-facts">
            <div className="system-fact">
              <dt>{E.model}</dt>
              <dd>{evals.model}</dd>
            </div>
            <div className="system-fact">
              <dt>{E.tasks}</dt>
              <dd>
                {evals.tasks.count === 0 ? (
                  E.none
                ) : (
                  <>
                    <span>{E.tasksLine(evals.tasks.count, evals.tasks.steps)}</span>
                    <span>{E.ended(evals.tasks.failed, evals.tasks.stopped, evals.tasks.step_limit)}</span>
                  </>
                )}
              </dd>
            </div>
            {evals.tasks.count > 0 && (
              <>
                <div className="system-fact">
                  <dt>{E.quality}</dt>
                  <dd>
                    <span>{E.answered(percent(evals.tasks.success_rate), evals.tasks.answered, evals.tasks.count)}</span>
                    <span>{E.stepsFailed(evals.tasks.steps_failed, evals.tasks.steps)}</span>
                    <span>{E.rated(evals.tasks.rated_good, evals.tasks.rated_bad)}</span>
                  </dd>
                </div>
                <div className="system-fact">
                  <dt>{E.latency}</dt>
                  <dd>
                    <span>{E.step(spanOf(evals.latency.tool.p50_ms), spanOf(evals.latency.tool.p95_ms))}</span>
                    <span>{E.reply(spanOf(evals.latency.model.p50_ms), spanOf(evals.latency.model.p95_ms))}</span>
                  </dd>
                </div>
                <div className="system-fact">
                  <dt>{E.time}</dt>
                  <dd>
                    <span>{E.task(spanOf(evals.time.task.p50_ms), spanOf(evals.time.task.p95_ms))}</span>
                    <span>{E.shares(percent(evals.time.model_share), percent(evals.time.tool_share), percent(evals.time.waiting_share))}</span>
                  </dd>
                </div>
                {evals.cost && (
                  <div className="system-fact">
                    <dt>{E.cost}</dt>
                    <dd>
                      {evals.cost.tasks_counted === 0 ? (
                        E.noTokens
                      ) : (
                        <>
                          <span>{E.tokens(count(evals.cost.input_tokens), count(evals.cost.output_tokens))}</span>
                          <span>{evals.cost.usd === null ? E.noPrice : E.dollars(dollars(evals.cost.usd), dollars(evals.cost.usd_per_task ?? 0))}</span>
                        </>
                      )}
                    </dd>
                  </div>
                )}
              </>
            )}
          </dl>

          {evals.latency.by_tool.length > 0 && (
            <>
              <h4 className="system-section">{E.performance}</h4>
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
            </>
          )}

          {may.checklist && (
            <>
              <h4 className="system-section">{E.checklist}</h4>
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
                      <Button icon="check" kind={task.rating === 'good' ? 'primary' : 'plain'} onClick={() => void rate(task, 'good')}>
                        {E.good}
                      </Button>
                      <Button icon="close" kind={task.rating === 'bad' ? 'primary' : 'plain'} onClick={() => void rate(task, 'bad')}>
                        {E.bad}
                      </Button>
                      <Button onClick={() => void showTrace(task)}>{trace?.id === task.id ? E.hideTrace : E.showTrace}</Button>
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
