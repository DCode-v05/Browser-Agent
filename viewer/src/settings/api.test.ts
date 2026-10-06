import { afterEach, describe, expect, it, vi } from 'vitest';

import { settingsFrom, SettingsUnreachable } from './api';

const ANSWER = { surface: 'web', groups: [] };
const PAGE = 'http://127.0.0.1:8765/';

function answering(...answers: { status: number; body?: unknown }[]) {
  const fetched = vi.fn<(address: string, how?: RequestInit) => Promise<unknown>>();
  for (const { status, body } of answers) fetched.mockResolvedValueOnce({ ok: status >= 200 && status < 300, status, json: async () => body });
  vi.stubGlobal('fetch', fetched);
  return fetched;
}

afterEach(() => vi.unstubAllGlobals());

describe('the settings of a live session (spec 10.2)', () => {
  it('are read from the service, with the token in a header and never in the address', async () => {
    const fetched = answering({ status: 200, body: ANSWER });
    expect(await settingsFrom(PAGE, 'the-token').load('mobile')).toEqual(ANSWER);
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/settings?surface=mobile');
    expect(how).toMatchObject({ headers: { Authorization: 'Bearer the-token' }, cache: 'no-store' });
  });

  it('are saved by the service, which answers with the settings as they are now', async () => {
    const fetched = answering({ status: 200, body: ANSWER });
    expect(await settingsFrom(PAGE, 'the-token').change('web', { colour_mode: 'dark' })).toEqual({ ok: true, answer: ANSWER });
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/settings');
    expect(how).toMatchObject({ method: 'PATCH', headers: { Authorization: 'Bearer the-token', 'Content-Type': 'application/json' } });
    expect(JSON.parse(String(how?.body))).toEqual({ surface: 'web', changes: { colour_mode: 'dark' } });
  });

  it('say which setting was refused, and why', async () => {
    answering({ status: 409, body: { setting: 'page_scripts', reason: 'would_loosen' } });
    expect(await settingsFrom(PAGE, 'the-token').change('web', { page_scripts: true })).toEqual({ ok: false, setting: 'page_scripts', reason: 'would_loosen' });
  });

  it('do not pass off a service that failed as a change that was saved', async () => {
    answering({ status: 500 });
    await expect(settingsFrom(PAGE, 'the-token').change('web', { colour_mode: 'dark' })).rejects.toBeInstanceOf(SettingsUnreachable);
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    await expect(settingsFrom(PAGE, 'the-token').change('web', { colour_mode: 'dark' })).rejects.toBeInstanceOf(SettingsUnreachable);
    await expect(settingsFrom(PAGE, 'the-token').load('web')).rejects.toBeInstanceOf(SettingsUnreachable);
  });

  it('cannot be read from a service that has none to give', async () => {
    answering({ status: 404 });
    await expect(settingsFrom(PAGE, 'the-token').load('web')).rejects.toBeInstanceOf(SettingsUnreachable);
  });

  it('ask the service to clear the browsing data, and do not say it is gone when it is not', async () => {
    const fetched = answering({ status: 200, body: { sessions_ended: 1, profile_cleared: true } }, { status: 409, body: { setting: 'clear_browsing_data', reason: 'locked' } });
    await settingsFrom(PAGE, 'the-token').run('web', 'clear_browsing_data');
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/browsing-data/clear');
    expect(how).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-token' } });
    await expect(settingsFrom(PAGE, 'the-token').run('web', 'clear_browsing_data')).rejects.toBeInstanceOf(SettingsUnreachable);
    // An action this build does not know asks for nothing.
    await settingsFrom(PAGE, 'the-token').run('web', 'something_else');
    expect(fetched).toHaveBeenCalledTimes(2);
  });

  it('read what About this deployment lists', async () => {
    const about = { version: '0.1.0', browser: 'Chromium 153', changed: [] };
    const fetched = answering({ status: 200, body: about });
    expect(await settingsFrom(PAGE, 'the-token').config()).toEqual(about);
    expect(fetched.mock.calls[0][0]).toBe('http://127.0.0.1:8765/api/config');
  });
});
