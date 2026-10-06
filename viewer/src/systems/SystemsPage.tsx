// The three browsers as systems (spec 9.17, 12.6): for each, whether it is in use, what the agent may
// do in it, its log, and what its tasks took. Everything here is drawn from what the service answers.

import { useCallback, useEffect, useState } from 'react';

import { Icon, type IconName } from '../components/Icon';
import { SettingsScreen } from '../components/SettingsScreen';
import { Button } from '../components/StatusPanel';
import type { Backend, Surface } from '../protocol';
import type { Setting, SettingsAnswer } from '../settings/types';
import { W } from '../wording';
import type { Check, Evals, LogAnswer, SystemAction, SystemInfo, SystemsApi, TaskRow, TaskTrace } from './api';
import { clock, count, dollars, percent, spanOf } from './format';

const BACKEND_ICON: Record<Backend, IconName> = {
  remote_headless: 'globe',
  takeover_chrome: 'person',
  bundled_chromium: 'monitor',
};
/** The states in which a system has no session. */
const NOT_RUNNING = new Set(['starting', 'waiting', 'failed', 'off', 'ended']);
/** How many lines of a log are shown at once. The file holds the rest. */
const LOG_LINES_SHOWN = 20;

type View = 'configuration' | 'evaluations';

interface Props {
  api: SystemsApi;
  surface: Surface;
  /** How often the service is asked where the systems stand, in milliseconds. 0 asks once. */
  pollMs: number;
  /** The word for where a system stands, as its tab says it. */
  wordFor(system: SystemInfo): string;
}

export function SystemsPage({ api, surface, pollMs, wordFor }: Props) {
  const [view, setView] = useState<View>('configuration');
  const [systems, setSystems] = useState<SystemInfo[] | null>(null);
  const [failed, setFailed] = useState(false);
  /** What a settings screen opened from here has to say, such as that data was cleared. */
  const [said, setSaid] = useState('');

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
        <div className="systems-grid">
          {systems.map((system) =>
            view === 'configuration' ? (
              <Configuration key={system.id} system={system} api={api} surface={surface} word={wordFor(system)} onChanged={load} onToast={setSaid} />
            ) : (
              <Evaluation key={system.id} system={system} api={api} word={wordFor(system)} />
            ),
          )}
        </div>
      )}
    </section>
  );
}

function CardHead({ system, word }: { system: SystemInfo; word: string }) {
  return (
    <header className="system-head">
      <Icon name={BACKEND_ICON[system.backend]} size="large" />
      <h3 className="system-name">{W.backend[system.backend]}</h3>
      <span className="system-state" data-on={system.enabled && !NOT_RUNNING.has(system.state)}>
        <span className="studio-tab-dot" aria-hidden="true" />
        {word}
      </span>
    </header>
  );
}

function Switch({ label, on, locked, onChange }: { label: string; on: boolean; locked?: boolean; onChange(next: boolean): void }) {
  return (
    <button type="button" role="switch" className="switch" aria-checked={on} aria-label={label} disabled={locked} onClick={() => onChange(!on)}>
      <span className="switch-knob" aria-hidden="true" />
      <span className="switch-word" aria-hidden="true">
        {on ? W.settings.on : W.settings.off}
      </span>
    </button>
  );
}

/** What a setting that is not a switch is set to, in the words its choices use. */
function chosen(setting: Setting): string {
  if (Array.isArray(setting.value)) return W.systems.sites(setting.value.length + (setting.fixed?.length ?? 0));
  return setting.choices?.find((choice) => choice.value === setting.value)?.label ?? String(setting.value ?? '');
}

interface ConfigurationProps {
  system: SystemInfo;
  api: SystemsApi;
  surface: Surface;
  word: string;
  onChanged(): Promise<void>;
  onToast(text: string): void;
}

function Configuration({ system, api, surface, word, onChanged, onToast }: ConfigurationProps) {
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
      <h4 className="system-section">{W.systems.records}</h4>
      <code className="system-path">{system.records}</code>

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

function LogLines({ log }: { log: LogAnswer }) {
  const lines = log.lines.slice(-LOG_LINES_SHOWN).reverse();
  if (lines.length === 0) return <p className="system-note">{W.systems.logEmpty}</p>;
  return (
    <div className="system-log">
      <p className="system-note">{W.systems.logNewest(lines.length)}</p>
      <ol className="system-log-lines">
        {lines.map((line, index) => (
          <li key={`${line.ts}-${index}`} className="system-log-line" data-ok={line.ok}>
            <span className="system-log-when">{clock(line.ts)}</span>
            <span className="system-log-tool">{line.tool.replace('browser_', '')}</span>
            <span className="system-log-took">
              {line.ok ? W.systems.worked : W.systems.didNot}, {spanOf(line.ms)}
            </span>
            <span className="system-log-said">{line.result}</span>
          </li>
        ))}
      </ol>
    </div>
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

          {evals.recent.length > 0 && (
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
