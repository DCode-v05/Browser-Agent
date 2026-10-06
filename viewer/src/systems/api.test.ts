import { afterEach, describe, expect, it, vi } from 'vitest';

import { systemsFrom } from './api';

const PAGE = 'http://127.0.0.1:8765/';
const UNREACHABLE = 'The service did not answer. Try again.';

function answering(...answers: { status: number; body?: unknown }[]) {
  const fetched = vi.fn<(address: string, how?: RequestInit) => Promise<unknown>>();
  for (const { status, body } of answers) fetched.mockResolvedValueOnce({ ok: status >= 200 && status < 300, status, json: async () => body });
  vi.stubGlobal('fetch', fetched);
  return fetched;
}

afterEach(() => vi.unstubAllGlobals());

const api = () => systemsFrom(PAGE, 'the-token', UNREACHABLE);

describe('what the window asks the service of its systems (spec 9.17)', () => {
  it('reads them with the token in a header, never in the address', async () => {
    const fetched = answering({ status: 200, body: { systems: [{ id: 'cloud' }] } }, { status: 404 });
    expect(await api().list()).toEqual([{ id: 'cloud' }]);
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/systems');
    expect(how).toMatchObject({ headers: { Authorization: 'Bearer the-token' }, cache: 'no-store' });
    // A service that has no systems, or does not answer, has none to list.
    expect(await api().list()).toBeNull();
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    expect(await api().list()).toBeNull();
  });

  it('reads a system’s log, what its tasks took, and the trace of one', async () => {
    const fetched = answering({ status: 200, body: { path: '/l', lines: [], size: 0 } }, { status: 200, body: { system: 'cloud' } }, { status: 200, body: { id: 't1', spans: [] } }, { status: 404 });
    expect(await api().log('cloud')).toEqual({ path: '/l', lines: [], size: 0 });
    expect(await api().evals('cloud')).toEqual({ system: 'cloud' });
    expect(await api().trace('cloud', 't1')).toEqual({ id: 't1', spans: [] });
    expect(await api().trace('cloud', 'none')).toBeNull();
    expect(fetched.mock.calls.map(([address]) => address)).toEqual([
      'http://127.0.0.1:8765/api/systems/cloud/log',
      'http://127.0.0.1:8765/api/systems/cloud/evals',
      'http://127.0.0.1:8765/api/systems/cloud/evals/t1',
      'http://127.0.0.1:8765/api/systems/cloud/evals/none',
    ]);
  });

  it('starts, stops and restarts a system, and passes on why it could not', async () => {
    const fetched = answering({ status: 200, body: { systems: [] } }, { status: 409, body: { error: 'This browser is running already.' } }, { status: 500 });
    expect(await api().manage('builtin', 'restart')).toEqual({ ok: true });
    expect(await api().manage('builtin', 'start')).toEqual({ ok: false, why: 'This browser is running already.' });
    expect(await api().manage('builtin', 'stop')).toEqual({ ok: false, why: UNREACHABLE });
    const [address, how] = fetched.mock.calls[0];
    expect(address).toBe('http://127.0.0.1:8765/api/systems/builtin/restart');
    expect(how).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-token' } });
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('no network')));
    expect(await api().manage('builtin', 'stop')).toEqual({ ok: false, why: UNREACHABLE });
  });

  it('runs the checklist, and says a person’s word on an answer', async () => {
    const checklist = { ran: 1, duration_ms: 2, passed: 1, failed: 0, skipped: 0, checks: [] };
    const fetched = answering({ status: 200, body: checklist }, { status: 409, body: { error: 'This browser is busy.' } }, { status: 200, body: { rating: 'good' } }, { status: 404 });
    expect(await api().check('cloud')).toEqual({ ok: true, result: checklist });
    expect(await api().check('cloud')).toEqual({ ok: false, why: 'This browser is busy.' });
    expect(await api().rate('cloud', 't1', 'good')).toBe(true);
    expect(await api().rate('cloud', 't9', null)).toBe(false);
    expect(fetched.mock.calls[0][0]).toBe('http://127.0.0.1:8765/api/systems/cloud/checks');
    const [address, how] = fetched.mock.calls[2];
    expect(address).toBe('http://127.0.0.1:8765/api/systems/cloud/evals/t1/rating');
    expect(how).toMatchObject({ method: 'POST', headers: { Authorization: 'Bearer the-token', 'Content-Type': 'application/json' } });
    expect(JSON.parse(String(how?.body))).toEqual({ rating: 'good' });
    expect(JSON.parse(String(fetched.mock.calls[3][1]?.body))).toEqual({ rating: null });
  });

  it('gives each system settings of its own, and the same ones each time', async () => {
    const fetched = answering({ status: 200, body: { surface: 'web', system: 'chrome', groups: [] } }, { status: 200, body: { surface: 'web', system: 'chrome', groups: [] } });
    const systems = api();
    expect(systems.settings('chrome')).toBe(systems.settings('chrome'));
    expect(systems.settings('chrome')).not.toBe(systems.settings('cloud'));
    await systems.settings('chrome').load('web');
    await systems.settings('chrome').change('web', { system_enabled: false });
    expect(fetched.mock.calls[0][0]).toBe('http://127.0.0.1:8765/api/settings?surface=web&system=chrome');
    expect(JSON.parse(String(fetched.mock.calls[1][1]?.body))).toEqual({ surface: 'web', system: 'chrome', changes: { system_enabled: false } });
  });
});
