// Signing in (spec 4.11): the admin and the user each have a page and a password of their own.
// A password is sent once, to sign in, and is never kept by the page.

export type Role = 'admin' | 'user';

export interface AuthState {
  /** Whether there is a password to sign in with, for each role. */
  admin_set: boolean;
  user_set: boolean;
  /** Who the page's own token speaks for, when it has one that still holds. */
  role: Role | null;
  /** The token is the service's own: the link the service printed when it started. */
  operator: boolean;
}

export type SignedIn = { ok: true; token: string } | { ok: false; why: 'wrong' | 'not_set' | 'unreachable' } | { ok: false; why: 'locked'; waitS: number };

export type PasswordSet = { ok: true } | { ok: false; why: string | null };

export interface AuthApi {
  /** `no_accounts` for a service nobody signs in to: its own token is the one way in. Null when it did not answer. */
  state(token: string | null): Promise<AuthState | 'no_accounts' | null>;
  signIn(role: Role, password: string): Promise<SignedIn>;
  /** For the admin: their own password, or the one users sign in with. `why` is the service's own sentence. */
  setPassword(token: string, role: Role, password: string): Promise<PasswordSet>;
  signOut(token: string): Promise<void>;
}

export function authFrom(pageAddress: string): AuthApi {
  const at = (path: string) => new URL(`api/auth${path}`, pageAddress).href;
  const json = { 'Content-Type': 'application/json' };

  return {
    async state(token) {
      try {
        const answer = await fetch(at(''), { headers: token ? { Authorization: `Bearer ${token}` } : {}, cache: 'no-store' });
        if (answer.status === 404) return 'no_accounts';
        if (!answer.ok) return null;
        const said = (await answer.json()) as AuthState & { accounts?: boolean };
        return said.accounts === false ? 'no_accounts' : said;
      } catch {
        return null;
      }
    },

    async signIn(role, password) {
      try {
        const answer = await fetch(at('/sign-in'), { method: 'POST', headers: json, body: JSON.stringify({ role, password }), cache: 'no-store' });
        const said = (await answer.json().catch(() => null)) as { token?: unknown; error?: unknown; wait_s?: unknown } | null;
        if (answer.ok && typeof said?.token === 'string') return { ok: true, token: said.token };
        if (answer.status === 429) return { ok: false, why: 'locked', waitS: typeof said?.wait_s === 'number' ? said.wait_s : 0 };
        if (answer.status === 401) return { ok: false, why: 'wrong' };
        if (answer.status === 409) return { ok: false, why: 'not_set' };
        return { ok: false, why: 'unreachable' };
      } catch {
        return { ok: false, why: 'unreachable' };
      }
    },

    async setPassword(token, role, password) {
      try {
        const answer = await fetch(at('/password'), { method: 'POST', headers: { ...json, Authorization: `Bearer ${token}` }, body: JSON.stringify({ role, password }), cache: 'no-store' });
        if (answer.ok) return { ok: true };
        const said = (await answer.json().catch(() => null)) as { error?: unknown } | null;
        return { ok: false, why: typeof said?.error === 'string' ? said.error : null };
      } catch {
        return { ok: false, why: null };
      }
    },

    async signOut(token) {
      try {
        await fetch(at('/sign-out'), { method: 'POST', headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
      } catch {
        // The page forgets its token either way.
      }
    },
  };
}
