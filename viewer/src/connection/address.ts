const TOKEN_KEY = 'bap-browser.token';

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

export function socketAddress(pageAddress: string, session: string): string {
  const address = new URL(`api/sessions/${encodeURIComponent(session)}/ws`, pageAddress);
  address.protocol = address.protocol === 'https:' ? 'wss:' : 'ws:';
  return address.href;
}
