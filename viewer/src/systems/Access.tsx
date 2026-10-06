// What only the admin has (spec 4.11): the policy for users (what they may change and see), the
// two passwords, and the evaluations of every system as one.

import { useId, useState, type FormEvent } from 'react';

import type { PasswordSet, Role } from '../auth/api';
import { Icon } from '../components/Icon';
import { Button } from '../components/StatusPanel';
import { W } from '../wording';
import type { Overall, Policy, PolicyChange, PolicyLine } from './api';
import { count, dollars, percent, spanOf } from './format';
import { Switch } from './parts';

/** Sets a password: the admin's own, or the one users sign in with. */
export interface Passwords {
  set(role: Role, password: string): Promise<PasswordSet>;
}

interface AccessProps {
  policy: Policy;
  onPolicy(changes: PolicyChange): void;
  passwords?: Passwords;
}

export function Access({ policy, onPolicy, passwords }: AccessProps) {
  const A = W.systems.access;
  const lines = (part: 'may_change' | 'sees', list: PolicyLine[]) =>
    list.map((line) => (
      <li key={line.id} className="system-row">
        <span className="system-row-name">{line.title ?? line.id}</span>
        <Switch label={`${A[part]}: ${line.title ?? line.id}`} on={line.allowed} onChange={(next) => onPolicy({ [part]: { [line.id]: next } })} />
      </li>
    ));
  return (
    <article className="system-card" aria-label={A.title}>
      <header className="system-head">
        <Icon name="lock" size="large" />
        <h3 className="system-name">{A.title}</h3>
      </header>
      <p className="system-note">{A.lead}</p>

      <h4 className="system-section">{A.may_change}</h4>
      <p className="system-note">{A.mayChangeLead}</p>
      <ul className="system-list">{lines('may_change', policy.may_change)}</ul>

      <h4 className="system-section">{A.sees}</h4>
      <ul className="system-list">{lines('sees', policy.sees)}</ul>

      {passwords && (
        <>
          <h4 className="system-section">{A.signIn}</h4>
          <PasswordForm role="user" passwords={passwords} />
          <PasswordForm role="admin" passwords={passwords} />
        </>
      )}
    </article>
  );
}

function PasswordForm({ role, passwords }: { role: Role; passwords: Passwords }) {
  const A = W.systems.access;
  const [password, setPassword] = useState('');
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    const done = await passwords.set(role, password);
    setBusy(false);
    if (done.ok) setPassword('');
    setSaid(done.ok ? { ok: true, text: A.saved[role] } : { ok: false, text: done.why ?? W.systems.unreachable });
  }

  return (
    <form className="system-password" onSubmit={(event) => void submit(event)}>
      <label className="system-row-name" htmlFor={id}>
        {A.password[role]}
      </label>
      <div className="system-password-row">
        <input id={id} className="sign-in-input" type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button type="submit" className="button" data-kind="plain" aria-busy={busy || undefined} aria-disabled={busy || undefined}>
          {A.set[role]}
        </button>
      </div>
      {said && (
        <p className="system-note" role="status" data-tone={said.ok ? 'success' : 'danger'}>
          {said.text}
        </p>
      )}
    </form>
  );
}

/** The tasks of every system as one, with a line for each system: the admin's view of the whole (spec 12.6). */
export function OverallCard({ overall, nameOf, onRefresh }: { overall: Overall | null; nameOf(system: string): string; onRefresh(): void }) {
  const O = W.systems.overall;
  const E = W.systems.evals;
  return (
    <article className="system-card" aria-label={O.title} data-wide="true">
      <header className="system-head">
        <Icon name="globe" size="large" />
        <h3 className="system-name">{O.title}</h3>
      </header>
      <div className="system-actions">
        <Button onClick={onRefresh}>{W.systems.refresh}</Button>
      </div>
      {overall === null ? (
        <p className="system-note" role="status">
          {W.systems.loading}
        </p>
      ) : overall.tasks.count === 0 ? (
        <p className="system-note">{O.none}</p>
      ) : (
        <>
          <dl className="system-facts">
            <div className="system-fact">
              <dt>{E.tasks}</dt>
              <dd>
                <span>{E.tasksLine(overall.tasks.count, overall.tasks.steps)}</span>
                <span>{E.answered(percent(overall.tasks.success_rate), overall.tasks.answered, overall.tasks.count)}</span>
              </dd>
            </div>
            <div className="system-fact">
              <dt>{E.latency}</dt>
              <dd>
                <span>{E.step(spanOf(overall.latency.tool.p50_ms), spanOf(overall.latency.tool.p95_ms))}</span>
                <span>{E.reply(spanOf(overall.latency.model.p50_ms), spanOf(overall.latency.model.p95_ms))}</span>
              </dd>
            </div>
            <div className="system-fact">
              <dt>{E.time}</dt>
              <dd>
                <span>{E.task(spanOf(overall.time.task.p50_ms), spanOf(overall.time.task.p95_ms))}</span>
                <span>{E.shares(percent(overall.time.model_share), percent(overall.time.tool_share), percent(overall.time.waiting_share))}</span>
              </dd>
            </div>
            <div className="system-fact">
              <dt>{E.cost}</dt>
              <dd>
                <span>{E.tokens(count(overall.cost.input_tokens), count(overall.cost.output_tokens))}</span>
                <span>{overall.cost.usd === null ? E.noPrice : E.dollars(dollars(overall.cost.usd), dollars(overall.cost.usd_per_task ?? 0))}</span>
              </dd>
            </div>
          </dl>
          <h4 className="system-section">{O.bySystem}</h4>
          <table className="system-table">
            <thead>
              <tr>
                <th scope="col">{O.system}</th>
                <th scope="col">{E.tasks}</th>
                <th scope="col">{O.answered}</th>
                <th scope="col">{O.typicalTask}</th>
                <th scope="col">{O.tokens}</th>
                <th scope="col">{E.cost}</th>
                <th scope="col">{E.checklist}</th>
              </tr>
            </thead>
            <tbody>
              {overall.systems.map((line) => (
                <tr key={line.system}>
                  <th scope="row">{nameOf(line.system)}</th>
                  <td>{line.tasks}</td>
                  <td>{percent(line.success_rate)}</td>
                  <td>{spanOf(line.task_p50_ms)}</td>
                  <td>{count(line.input_tokens + line.output_tokens)}</td>
                  <td>{line.usd === null ? '–' : dollars(line.usd)}</td>
                  <td>{line.checks === null ? O.notRun : E.passed(line.checks_passed ?? 0, line.checks)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </article>
  );
}
