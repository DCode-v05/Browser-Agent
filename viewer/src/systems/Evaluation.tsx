// What one browser's tasks took, its checklist, its task sets and the trace of each task (spec 12.6,
// 12.7). Drawn from what the service answers, and from what the admin lets this person see.

import { useCallback, useEffect, useState, type ReactNode } from 'react';

import { Icon } from '../components/Icon';
import { Button } from '../components/StatusPanel';
import { W } from '../wording';
import type { Check, Evals, Me, SystemInfo, SystemsApi, TaskRow, TaskTrace } from './api';
import { SuiteCard } from './Suite';
import { clock, count, dollars, percent, spanOf } from './format';
import { CardHead, TableScroll } from './parts';

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

export function Evaluation({ system, api, word, sees }: { system: SystemInfo; api: SystemsApi; word: string; sees?: Me['sees'] }) {
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

          {may.checklist && <SuiteCard system={system.id} api={api} />}

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
