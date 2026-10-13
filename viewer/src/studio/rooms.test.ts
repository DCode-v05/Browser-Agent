// The chat above every app (spec 22.3.1): the page asks the service on this machine for a window of
// its own, and where there is none to give it opens the chat in a window of the browser's.

import { afterEach, describe, expect, it, vi } from 'vitest';

import { besideOpener } from './rooms';

afterEach(() => vi.unstubAllGlobals());

describe('the chat beside the screen', () => {
  it('is asked of the service, for the page it is of, with the token in a header', async () => {
    const asked = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', asked);
    const inTheBrowser = vi.fn();

    await besideOpener('http://127.0.0.1:8765/?x=1', 'a-visit', inTheBrowser)('computer');

    expect(asked).toHaveBeenCalledWith('http://127.0.0.1:8765/api/sessions/computer/beside', { method: 'POST', headers: { Authorization: 'Bearer a-visit' }, cache: 'no-store' });
    expect(inTheBrowser).not.toHaveBeenCalled();
  });

  it('opens in a window of the browser where the service has no window to give', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
    const inTheBrowser = vi.fn();

    await besideOpener('http://vm.example.ts.net/', 'a-visit', inTheBrowser)('computer');

    expect(inTheBrowser).toHaveBeenCalledWith('computer');
  });

  it('opens in a window of the browser when the service does not answer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')));
    const inTheBrowser = vi.fn();

    await besideOpener('http://127.0.0.1:8765/', 'a-visit', inTheBrowser)('computer');

    expect(inTheBrowser).toHaveBeenCalledWith('computer');
  });
});
