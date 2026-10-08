// The task sets of a browser (spec 12.7): tasks with a known right end, run on the practice site
// and graded by code. A person starts a run, watches where it is, stops it, and reads how it went.

import { useCallback, useEffect, useState } from 'react';

import { Icon } from '../components/Icon';
import { Button } from '../components/StatusPanel';
import { W } from '../wording';
import type { SetName, SuiteAnswer, SuiteMode, SuiteOverall, SuiteRun, SuiteSet, SuiteTotals, SystemsApi } from './api';
import { count, dollars, percent, spanOf } from './format';
import { TableScroll } from './parts';

const S = W.systems.suite;
/** How often a run under way is asked about. */
const RUNNING_POLL_MS = 1500;

/** The day and the time a run began. */
function when(seconds: number): string {
  return new Date(seconds * 1000).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

/** What a run of a set came to, in the one number the set is for; and whether that is good. */
export function headline(set: SetName, totals: SuiteTotals): { text: string; tone: 'success' | 'danger' } {
  if (set === 'attack') {
    return { text: S.followed(totals.attacks_followed, totals.attacks, percent(totals.attack_rate)), tone: totals.attacks_followed > 0 ? 'danger' : 'success' };
  }
  if (set === 'confirm') {
    const missed = totals.ask_recall !== null && totals.ask_recall < 1;
    return { text: S.asked(percent(totals.ask_recall), percent(totals.needless_asks)), tone: missed ? 'danger' : 'success' };
  }
  return { text: S.passed(totals.passed, totals.trials, percent(totals.pass_rate)), tone: totals.passed < totals.trials ? 'danger' : 'success' };
}

/** The one number of a run, for a table that compares browsers. */
export function short(set: SetName, totals: SuiteTotals): string {
  if (set === 'attack') return S.cell.attack(percent(totals.attack_rate));
  if (set === 'confirm') return S.cell.confirm(percent(totals.ask_recall));
  return S.cell.passed(percent(totals.pass_rate));
}

export function SuiteCard({ system, api }: { system: string; api: SystemsApi }) {
  const [suite, setSuite] = useState<SuiteAnswer | null>(null);
  const [failed, setFailed] = useState(false);
  const [note, setNote] = useState('');
  const [trials, setTrials] = useState<number | null>(null);
  const [open, setOpen] = useState<SetName | null>(null);
  /** The run a person has just asked for, until the service says it is under way. */
  const [asking, setAsking] = useState<SetName | null>(null);

  const show = useCallback((told: SuiteAnswer | null) => {
    setFailed(told === null);
    if (told) setSuite(told);
  }, []);

  useEffect(() => {
    let current = true;
    void api.suite(system).then((told) => current && show(told));
    return () => {
      current = false;
    };
  }, [api, show, system]);

  // While a run is under way, where it is is asked again and again.
  const running = suite?.running ?? null;
  const underWay = running !== null;
  useEffect(() => {
    if (!underWay) return;
    let current = true;
    const timer = setInterval(() => void api.suite(system).then((told) => current && show(told)), RUNNING_POLL_MS);
    return () => {
      current = false;
      clearInterval(timer);
    };
  }, [api, show, system, underWay]);

  async function run(set: SetName, mode: SuiteMode) {
    if (!suite) return;
    setNote('');
    setAsking(set);
    const done = await api.runSuite(system, set, trials ?? suite.trials, mode);
    setAsking(null);
    if (done.ok) show(done.result);
    else setNote(done.why);
  }

  async function stop() {
    const done = await api.stopSuite(system);
    if (done.ok) show(done.result);
    else setNote(done.why);
  }

  if (suite === null) {
    return (
      <>
        <h4 className="system-section">{S.title}</h4>
        <p className="system-note" role="status">
          {failed ? W.systems.unreachable : W.systems.loading}
        </p>
      </>
    );
  }
  const tries = [1, 3, 5, 10].filter((n) => n <= suite.max_trials);
  const busy = running !== null || asking !== null;
  return (
    <>
      <h4 className="system-section">{S.title}</h4>
      <p className="system-hint">{S.lead}</p>
      <label className="suite-tries">
        <span>{S.tries}</span>
        <select className="suite-select" value={trials ?? suite.trials} title={S.triesHint} disabled={busy} onChange={(event) => setTrials(Number(event.target.value))}>
          {tries.map((n) => (
            <option key={n} value={n}>
              {S.times(n)}
            </option>
          ))}
        </select>
      </label>
      {note && (
        <p className="system-note" role="status" data-tone="danger">
          {note}
        </p>
      )}
      <ul className="suite-sets">
        {suite.sets.map((set) => (
          <SetBlock
            key={set.id}
            set={set}
            running={running?.set === set.id ? running : null}
            busy={busy}
            asking={asking === set.id}
            open={open === set.id}
            onToggle={() => setOpen(open === set.id ? null : set.id)}
            onRun={(mode) => void run(set.id, mode)}
            onStop={() => void stop()}
          />
        ))}
      </ul>
    </>
  );
}

interface SetProps {
  set: SuiteSet;
  running: SuiteAnswer['running'];
  busy: boolean;
  asking: boolean;
  open: boolean;
  onToggle(): void;
  onRun(mode: SuiteMode): void;
  onStop(): void;
}

function SetBlock({ set, running, busy, asking, open, onToggle, onRun, onStop }: SetProps) {
  const last = set.last;
  const told = last ? headline(set.id, last.totals) : null;
  return (
    <li className="suite-set" aria-label={set.title}>
      <div className="suite-set-head">
        <h5 className="suite-set-title">{set.title}</h5>
        <span className="suite-set-size">{S.tasks(set.tasks)}</span>
      </div>
      <p className="system-hint">{set.lead}</p>
      {running ? (
        <p className="system-note" role="status" data-tone="running">
          {running.stopping ? S.stopping : S.progress(running.task, running.tasks, running.trial, running.trials, running.title)}
        </p>
      ) : last && told ? (
        <>
          <p className="system-note" data-tone={told.tone}>
            <Icon name={told.tone === 'success' ? 'check' : 'alert'} /> {told.text}
          </p>
          <p className="system-hint">
            {S.ran(S.mode[last.mode], when(last.started), last.trials, spanOf(last.duration_ms))}
            {last.mode === 'agent' && last.model ? ` ${S.model(last.model)}` : ''}
            {set.id !== 'confirm' && set.id !== 'attack' && last.trials > 1 ? ` ${S.everyTime(last.totals.every_time, last.totals.tasks)}` : ''}
            {set.id === 'attack' && last.totals.attacks_followed > 0 ? ` ${S.attacksAsked(last.totals.attacks_asked, last.totals.attacks_followed)}` : ''}
            {last.totals.input_tokens > 0 ? ` ${S.tokens(count(last.totals.input_tokens), count(last.totals.output_tokens))}` : ''}
            {last.totals.cost_usd !== null ? ` ${S.cost(dollars(last.totals.cost_usd))}` : ''}
            {last.stopped ? ` ${S.stopped(last.totals.tasks, last.of)}` : ''}
          </p>
          {set.earlier.length > 0 && <p className="system-hint">{S.earlier(set.earlier.map((run) => (set.id === 'attack' ? percent(run.attack_rate) : percent(run.pass_rate))).join(', '))}</p>}
        </>
      ) : (
        <p className="system-note">{S.neverRun}</p>
      )}
      <div className="system-actions">
        {running ? (
          <Button kind="danger" icon="stop" hint={S.stopHint} disabled={running.stopping} onClick={onStop}>
            {S.stop}
          </Button>
        ) : (
          <>
            <Button kind="primary" icon="play" hint={S.runAgentHint} busy={asking} disabled={busy && !asking} onClick={() => onRun('agent')}>
              {S.runAgent}
            </Button>
            <Button icon="check" hint={S.runReferenceHint} disabled={busy} onClick={() => onRun('reference')}>
              {S.runReference}
            </Button>
          </>
        )}
        {last && (
          <Button hint={S.tasksHint} onClick={onToggle}>
            {open ? S.hideTasks : S.showTasks}
          </Button>
        )}
      </div>
      {open && last && <Tasks set={set.id} run={last} />}
    </li>
  );
}

function Tasks({ set, run }: { set: SetName; run: SuiteRun }) {
  return (
    <TableScroll label={S.tasksOf(run.set)}>
      <table className="system-table">
        <thead>
          <tr>
            <th scope="col">{S.column.task}</th>
            <th scope="col">{S.column.passed}</th>
            <th scope="col">{S.column.asked}</th>
            {set === 'attack' && <th scope="col">{S.column.followed}</th>}
            <th scope="col">{S.column.steps}</th>
            <th scope="col">{S.column.why}</th>
          </tr>
        </thead>
        <tbody>
          {run.tasks.map((task) => {
            const tries = task.trials.length;
            const failure = task.trials.find((trial) => !trial.passed);
            return (
              <tr key={task.id} data-passed={task.passed === tries}>
                <th scope="row">{task.title}</th>
                <td>{S.outOf(task.passed, tries)}</td>
                <td>{S.outOf(task.trials.filter((trial) => trial.asked > 0).length, tries)}</td>
                {set === 'attack' && <td>{S.outOf(task.trials.filter((trial) => trial.attacked === true).length, tries)}</td>}
                <td>{Math.round(task.trials.reduce((sum, trial) => sum + trial.steps, 0) / Math.max(tries, 1))}</td>
                <td>{failure ? failure.why : ''}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </TableScroll>
  );
}

/** The newest run of each set on each browser, side by side: the admin's view of the whole. */
export function ParityCard({ overall, nameOf, onRefresh }: { overall: SuiteOverall | null; nameOf(system: string): string; onRefresh(): void }) {
  const P = S.parity;
  const ran = overall?.systems.some((system) => Object.keys(system.runs).length > 0) ?? false;
  return (
    <article className="system-card" aria-label={P.title} data-wide="true">
      <header className="system-head">
        <Icon name="check" size="large" />
        <h3 className="system-name">{P.title}</h3>
      </header>
      <p className="system-hint">{P.lead}</p>
      <div className="system-actions">
        <Button hint={W.systems.refreshHint} onClick={onRefresh}>
          {W.systems.refresh}
        </Button>
      </div>
      {overall === null ? (
        <p className="system-note" role="status">
          {W.systems.loading}
        </p>
      ) : !ran ? (
        <p className="system-note">{P.none}</p>
      ) : (
        <TableScroll label={P.title}>
          <table className="system-table">
            <thead>
              <tr>
                <th scope="col">{P.set}</th>
                {overall.systems.map((system) => (
                  <th key={system.system} scope="col">
                    {nameOf(system.system)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {overall.sets.map((set) => (
                <tr key={set.id}>
                  <th scope="row">{set.title}</th>
                  {overall.systems.map((system) => {
                    const run = system.runs[set.id];
                    return (
                      <td key={system.system}>
                        {run ? (
                          <>
                            <span>{short(set.id, run)}</span>
                            <span className="system-check-detail">{P.how(S.mode[run.mode], when(run.started), run.trials)}</span>
                          </>
                        ) : (
                          P.notRun
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </TableScroll>
      )}
    </article>
  );
}
