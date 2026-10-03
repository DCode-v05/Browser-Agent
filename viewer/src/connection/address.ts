// What the viewer reads from its own address: the token that lets it in, and where the session is.

const TOKEN_KEY = 'bap-browser.token';

/**
 * The token arrives in the fragment, which is never sent to a server. It is kept for the life of
 * the tab and removed from the address bar (spec 4.10).
 */
export function takeToken(
  page: { hash: string; pathname: string; search: string },
  storage: Pick<Storage, 'getItem' | 'setItem'>,
  replaceAddress: (address: string) => void,
): string | null {
  const given = new URLSearchParams(page.hash.slice(1)).get('token');
  if (given) {
    try {
      storage.setItem(TOKEN_KEY, given);
    } catch {
      // A tab that can keep nothing still works until it is reloaded.
    }
    replaceAddress(page.pathname + page.search);
    return given;
  }
  try {
    return storage.getItem(TOKEN_KEY) || null;
  } catch {
    return null;
  }
}

/** The session's WebSocket, beside the page and under the same path. */
export function socketAddress(pageAddress: string, session: string): string {
  const address = new URL(`api/sessions/${encodeURIComponent(session)}/ws`, pageAddress);
  address.protocol = address.protocol === 'https:' ? 'wss:' : 'ws:';
  return address.href;
}
