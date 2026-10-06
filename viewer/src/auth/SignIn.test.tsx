import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { W } from '../wording';
import { authFrom, type AuthApi, type AuthState, type SignedIn } from './api';
import { SignIn } from './SignIn';

const S = W.signIn;
const BOTH_SET: AuthState = { admin_set: true, user_set: true, role: null, operator: false };

function page(role: 'admin' | 'user', state: AuthState, answers: SignedIn[] = [{ ok: true, token: 'a-visit' }], operator: string | null = null) {
  const api: AuthApi = {
    state: vi.fn(async () => state),
    signIn: vi.fn(async (): Promise<SignedIn> => answers.shift() ?? { ok: false, why: 'wrong' }),
    setPassword: vi.fn(async (_token: string, _role: string, password: string) => (password.length >= 8 ? ({ ok: true } as const) : ({ ok: false, why: 'Use at least 8 characters.' } as const))),
    signOut: vi.fn(async () => undefined),
  };
  const onSignedIn = vi.fn();
  const user = userEvent.setup();
  render(<SignIn role={role} state={state} api={api} operator={operator} onSignedIn={onSignedIn} otherPage={role === 'admin' ? '/' : '/admin'} />);
  return { api, onSignedIn, user };
}

describe('the two sign-in pages (spec 4.11)', () => {
  it('the user’s page asks for the users’ password, and signs in with it', async () => {
    const { api, onSignedIn, user } = page('user', BOTH_SET);
    expect(screen.getByRole('heading', { name: S.title.user })).toBeInTheDocument();
    expect(screen.getByText(S.role.user)).toBeInTheDocument();
    const box = screen.getByLabelText(S.password);
    // What is typed is not shown, and the page starts where the person types.
    expect(box).toHaveAttribute('type', 'password');
    expect(box).toHaveFocus();
    await user.type(box, 'what users sign in with{Enter}');
    expect(api.signIn).toHaveBeenCalledWith('user', 'what users sign in with');
    expect(onSignedIn).toHaveBeenCalledWith('a-visit');
    // The other page is one press away.
    expect(screen.getByRole('link', { name: S.other.user })).toHaveAttribute('href', '/admin');
  });

  it('the admin’s page is told apart, and signs in as the admin', async () => {
    const { api, onSignedIn, user } = page('admin', BOTH_SET);
    expect(screen.getByRole('heading', { name: S.title.admin })).toBeInTheDocument();
    expect(document.querySelector('.sign-in')).toHaveAttribute('data-role', 'admin');
    await user.type(screen.getByLabelText(S.password), 'the admin’s own words');
    await user.click(screen.getByRole('button', { name: S.button }));
    expect(api.signIn).toHaveBeenCalledWith('admin', 'the admin’s own words');
    expect(onSignedIn).toHaveBeenCalledWith('a-visit');
    expect(screen.getByRole('link', { name: S.other.admin })).toHaveAttribute('href', '/');
  });

  it('says a wrong password is wrong, forgets what was typed, and lets the person try again', async () => {
    const { onSignedIn, user } = page('user', BOTH_SET, [
      { ok: false, why: 'wrong' },
      { ok: true, token: 'a-visit' },
    ]);
    const box = screen.getByLabelText(S.password);
    await user.type(box, 'a guess at it{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent(S.failed.wrong);
    expect(box).toHaveValue('');
    expect(onSignedIn).not.toHaveBeenCalled();
    await user.type(box, 'what users sign in with{Enter}');
    expect(onSignedIn).toHaveBeenCalledWith('a-visit');
  });

  it('says how long to wait after too many wrong passwords, and when the service did not answer', async () => {
    const { user } = page('user', BOTH_SET, [
      { ok: false, why: 'locked', waitS: 42 },
      { ok: false, why: 'unreachable' },
    ]);
    await user.type(screen.getByLabelText(S.password), 'a guess at it{Enter}');
    expect(await screen.findByRole('alert')).toHaveTextContent(S.locked(42));
    await user.type(screen.getByLabelText(S.password), 'a guess at it{Enter}');
    expect(await screen.findByText(S.failed.unreachable)).toBeInTheDocument();
  });

  it('tells a user there is no password yet, and asks for none', () => {
    page('user', { ...BOTH_SET, user_set: false });
    expect(screen.getByText(S.userNotSet)).toBeInTheDocument();
    expect(screen.queryByLabelText(S.password)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: S.button })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: S.other.user })).toBeInTheDocument();
  });
});

describe('the first time: the admin’s password is made (spec 4.11)', () => {
  const FIRST: AuthState = { admin_set: false, user_set: false, role: 'admin', operator: true };

  it('is made with the link the service printed, typed twice, and signs the admin in', async () => {
    const { api, onSignedIn, user } = page('admin', FIRST, [{ ok: true, token: 'the-admins-visit' }], 'the-services-own-token');
    expect(screen.getByRole('heading', { name: S.create })).toBeInTheDocument();
    await user.type(screen.getByLabelText(S.newPassword), 'the admin’s own words');
    await user.type(screen.getByLabelText(S.again), 'the admin’s own word');
    await user.click(screen.getByRole('button', { name: S.createButton }));
    // Typed twice, and not the same: nothing is made of it.
    expect(await screen.findByRole('alert')).toHaveTextContent(S.notTheSame);
    expect(api.setPassword).not.toHaveBeenCalled();
    await user.type(screen.getByLabelText(S.again), 's');
    await user.click(screen.getByRole('button', { name: S.createButton }));
    expect(api.setPassword).toHaveBeenCalledWith('the-services-own-token', 'admin', 'the admin’s own words');
    expect(api.signIn).toHaveBeenCalledWith('admin', 'the admin’s own words');
    expect(onSignedIn).toHaveBeenCalledWith('the-admins-visit');
  });

  it('says what the service said of a password it did not take', async () => {
    const { onSignedIn, user } = page('admin', FIRST, [], 'the-services-own-token');
    await user.type(screen.getByLabelText(S.newPassword), 'short');
    await user.type(screen.getByLabelText(S.again), 'short');
    await user.click(screen.getByRole('button', { name: S.createButton }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Use at least 8 characters.');
    expect(onSignedIn).not.toHaveBeenCalled();
  });

  it('is not made by someone who does not hold that link', () => {
    page('admin', { admin_set: false, user_set: false, role: null, operator: false });
    expect(screen.getByText(S.adminNotMade)).toBeInTheDocument();
    expect(screen.queryByLabelText(S.newPassword)).not.toBeInTheDocument();
  });
});

describe('what a sign-in page asks the service', () => {
  const PAGE = 'http://127.0.0.1:8765/admin';

  function answering(...answers: { status: number; body?: unknown }[]) {
    const fetched = vi.fn<(address: string, how?: RequestInit) => Promise<unknown>>();
    for (const { status, body } of answers) fetched.mockResolvedValueOnce({ ok: status >= 200 && status < 300, status, json: async () => body });
    vi.stubGlobal('fetch', fetched);
    return fetched;
  }
  afterEach(() => vi.unstubAllGlobals());

  it('asks whether there is a password yet, and who its own token speaks for', async () => {
    const fetched = answering({ status: 200, body: BOTH_SET }, { status: 200, body: { accounts: false } }, { status: 404 }, { status: 500 });
    expect(await authFrom(PAGE).state('a-token')).toEqual(BOTH_SET);
    // The admin's page is one step below the service's own address: the API is beside it, not under it.
    expect(fetched.mock.calls[0][0]).toBe('http://127.0.0.1:8765/api/auth');
    expect(fetched.mock.calls[0][1]).toMatchObject({ headers: { Authorization: 'Bearer a-token' } });
    // A service nobody signs in to says so, and one that fails is not taken for one.
    expect(await authFrom(PAGE).state(null)).toBe('no_accounts');
    expect(await authFrom(PAGE).state(null)).toBe('no_accounts');
    expect(await authFrom(PAGE).state(null)).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    expect(await authFrom(PAGE).state(null)).toBeNull();
  });

  it('signs in with the password in the body of the request, never in the address', async () => {
    const fetched = answering({ status: 200, body: { token: 'a-visit', role: 'user' } }, { status: 401, body: { error: 'wrong' } }, { status: 409, body: { error: 'not_set' } }, { status: 429, body: { error: 'locked', wait_s: 30 } }, { status: 500 });
    const api = authFrom(PAGE);
    expect(await api.signIn('user', 'what users sign in with')).toEqual({ ok: true, token: 'a-visit' });
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/auth/sign-in');
    expect(address).not.toContain('what');
    expect(JSON.parse(String(how?.body))).toEqual({ role: 'user', password: 'what users sign in with' });
    expect(await api.signIn('user', 'x')).toEqual({ ok: false, why: 'wrong' });
    expect(await api.signIn('user', 'x')).toEqual({ ok: false, why: 'not_set' });
    expect(await api.signIn('user', 'x')).toEqual({ ok: false, why: 'locked', waitS: 30 });
    expect(await api.signIn('user', 'x')).toEqual({ ok: false, why: 'unreachable' });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    expect(await api.signIn('user', 'x')).toEqual({ ok: false, why: 'unreachable' });
  });

  it('sets a password as the admin, and signs out', async () => {
    const fetched = answering({ status: 200, body: {} }, { status: 400, body: { error: 'Use at least 8 characters.' } }, { status: 403 }, { status: 200, body: {} });
    const api = authFrom(PAGE);
    expect(await api.setPassword('the-admins-token', 'user', 'what users sign in with')).toEqual({ ok: true });
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/auth/password');
    expect(how).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-admins-token' } });
    expect(JSON.parse(String(how?.body))).toEqual({ role: 'user', password: 'what users sign in with' });
    expect(await api.setPassword('the-admins-token', 'user', 'short')).toEqual({ ok: false, why: 'Use at least 8 characters.' });
    expect(await api.setPassword('a-users-token', 'user', 'one they chose themselves')).toEqual({ ok: false, why: null });
    await api.signOut('the-admins-token');
    expect(fetched.mock.calls[3][0]).toBe('http://127.0.0.1:8765/api/auth/sign-out');
    expect(fetched.mock.calls[3][1]).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-admins-token' } });
  });
});
