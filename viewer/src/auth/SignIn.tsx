// The two sign-in pages (spec 4.11): one for the admin, at /admin, and one for users. The first
// time, the admin's page makes the admin's password instead of asking for it.

import { useId, useState, type FormEvent } from 'react';

import { Icon } from '../components/Icon';
import { W } from '../wording';
import type { AuthApi, AuthState, Role } from './api';

interface Props {
  role: Role;
  state: AuthState;
  api: AuthApi;
  /** The service's own token, when the page was opened with the link the service printed. */
  operator: string | null;
  /** The page signed in. The token is for the rest of the visit. */
  onSignedIn(token: string): void;
  /** Where the other page is. */
  otherPage: string;
}

export function SignIn({ role, state, api, operator, onSignedIn, otherPage }: Props) {
  const S = W.signIn;
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [said, setSaid] = useState('');
  const [busy, setBusy] = useState(false);
  const passwordId = useId();
  const againId = useId();
  const saidId = useId();

  const creating = role === 'admin' && !state.admin_set;
  // The admin's password is made with the link the service printed, and with nothing else.
  const cannot = creating && !(operator && state.operator) ? S.adminNotMade : role === 'user' && !state.user_set ? S.userNotSet : '';

  async function signIn() {
    const done = await api.signIn(role, password);
    if (done.ok) return onSignedIn(done.token);
    setPassword('');
    setSaid(done.why === 'locked' ? S.locked(done.waitS) : S.failed[done.why]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setSaid('');
    if (creating && password !== again) return setSaid(S.notTheSame);
    setBusy(true);
    if (creating && operator) {
      const made = await api.setPassword(operator, 'admin', password);
      if (!made.ok) {
        setBusy(false);
        return setSaid(made.why ?? S.failed.unreachable);
      }
    }
    await signIn();
    setBusy(false);
  }

  return (
    <main className="sign-in" data-role={role}>
      <form className="sign-in-card" onSubmit={(event) => void submit(event)} aria-labelledby={`${passwordId}-title`}>
        <span className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{W.product}</span>
        </span>
        <p className="sign-in-role">
          <Icon name={role === 'admin' ? 'settings' : 'person'} />
          {S.role[role]}
        </p>
        <h1 id={`${passwordId}-title`} className="sign-in-title">
          {creating ? S.create : S.title[role]}
        </h1>
        <p className="sign-in-lead">{creating ? S.createLead : S.lead[role]}</p>
        {cannot ? (
          <p className="sign-in-said" role="status">
            {cannot}
          </p>
        ) : (
          <>
            <label className="sign-in-label" htmlFor={passwordId}>
              {creating ? S.newPassword : S.password}
            </label>
            <input
              id={passwordId}
              className="sign-in-input"
              type="password"
              autoComplete={creating ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              aria-describedby={said ? saidId : undefined}
              autoFocus
              required
            />
            {creating && (
              <>
                <label className="sign-in-label" htmlFor={againId}>
                  {S.again}
                </label>
                <input id={againId} className="sign-in-input" type="password" autoComplete="new-password" value={again} onChange={(event) => setAgain(event.target.value)} required />
              </>
            )}
            {said && (
              <p id={saidId} className="sign-in-said" role="alert">
                {said}
              </p>
            )}
            <button type="submit" className="button" data-kind="primary" aria-busy={busy || undefined} aria-disabled={busy || undefined}>
              {creating ? S.createButton : S.button}
            </button>
          </>
        )}
        <a className="sign-in-other" href={otherPage}>
          {S.other[role]}
        </a>
      </form>
    </main>
  );
}
