import { describe, expect, it } from 'vitest';

import { socketAddress, takeToken } from './address';

function memory(initial: Record<string, string> = {}) {
  const kept = new Map(Object.entries(initial));
  return {
    kept,
    getItem: (key: string) => kept.get(key) ?? null,
    setItem: (key: string, value: string) => void kept.set(key, value),
  };
}

describe('the token', () => {
  it('is taken from the fragment, kept for the tab, and removed from the address bar', () => {
    const storage = memory();
    const shown: string[] = [];
    const token = takeToken({ hash: '#token=abc123', pathname: '/', search: '?session=default' }, storage, (address) => shown.push(address));
    expect(token).toBe('abc123');
    expect([...storage.kept.values()]).toEqual(['abc123']);
    expect(shown).toEqual(['/?session=default']);
  });

  it('is found again after a reload, when the address no longer carries it', () => {
    const storage = memory();
    takeToken({ hash: '#token=abc123', pathname: '/', search: '' }, storage, () => undefined);
    const shown: string[] = [];
    expect(takeToken({ hash: '', pathname: '/', search: '' }, storage, (address) => shown.push(address))).toBe('abc123');
    expect(shown).toEqual([]);
  });

  it('a new one in the address replaces the one kept', () => {
    const storage = memory();
    takeToken({ hash: '#token=old', pathname: '/', search: '' }, storage, () => undefined);
    expect(takeToken({ hash: '#token=new', pathname: '/', search: '' }, storage, () => undefined)).toBe('new');
    expect([...storage.kept.values()]).toEqual(['new']);
  });

  it('is missing when the page was opened without it', () => {
    expect(takeToken({ hash: '', pathname: '/', search: '' }, memory(), () => undefined)).toBeNull();
    expect(takeToken({ hash: '#token=', pathname: '/', search: '' }, memory(), () => undefined)).toBeNull();
  });

  it('still works where the tab cannot keep anything', () => {
    const refusing = {
      getItem: (): string | null => {
        throw new Error('blocked');
      },
      setItem: (): void => {
        throw new Error('blocked');
      },
    };
    expect(takeToken({ hash: '#token=abc123', pathname: '/', search: '' }, refusing, () => undefined)).toBe('abc123');
    expect(takeToken({ hash: '', pathname: '/', search: '' }, refusing, () => undefined)).toBeNull();
  });
});

describe("the session's address", () => {
  it('is the WebSocket beside the page', () => {
    expect(socketAddress('http://127.0.0.1:8765/', 'default')).toBe('ws://127.0.0.1:8765/api/sessions/default/ws');
  });

  it('is encrypted when the page is, and keeps the path the page is served under', () => {
    expect(socketAddress('https://vm-1234.example.app/browser/?session=s2', 's2')).toBe('wss://vm-1234.example.app/browser/api/sessions/s2/ws');
  });

  it('never carries a session name as anything but one path segment', () => {
    expect(socketAddress('http://127.0.0.1:8765/', '../x?y')).toBe('ws://127.0.0.1:8765/api/sessions/..%2Fx%3Fy/ws');
  });
});
