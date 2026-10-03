import { describe, expect, it } from 'vitest';

import type { SettingsAnswer } from '../settings/types';
import { createDemoSettings } from './settings';

const ids = (answer: SettingsAnswer) => answer.groups.flatMap((group) => group.settings.map((setting) => setting.id));
const find = (answer: SettingsAnswer, id: string) => answer.groups.flatMap((group) => group.settings).find((setting) => setting.id === id)!;

// The sets of spec 10.2. Web and mobile hold what milestone 1 builds; desktop shows its whole design.
const MOBILE = [
  'stay_signed_in',
  'ask_before',
  'approval_wait',
  'remember_site_approval',
  'blocked_sites',
  'allowed_sites',
  'allow_downloads',
  'allow_uploads',
  'activity_log',
  'clear_browsing_data',
  'picture_quality',
  'show_agent_pointer',
  'colour_mode',
];
const WEB = [...MOBILE, 'preferred_browser', 'page_scripts', 'about'];
const DESKTOP = [...WEB, 'my_chrome', 'show_builtin_browser', 'my_chrome_mode', 'approved_sites', 'download_folder', 'upload_folders'];

describe('the settings a surface receives', () => {
  it.each([
    ['web', WEB],
    ['mobile', MOBILE],
    ['desktop', DESKTOP],
  ] as const)('%s has exactly its set', async (surface, expected) => {
    const answer = await createDemoSettings().load(surface);
    expect(ids(answer).sort()).toEqual([...expected].sort());
    expect(answer.surface).toBe(surface);
  });

  it('web has 16 settings and mobile 13 in milestone 1, as the spec counts them', () => {
    expect(WEB).toHaveLength(16);
    expect(MOBILE).toHaveLength(13);
  });

  it('groups come in the order of spec 9.12, and an empty group is left out', async () => {
    const source = createDemoSettings();
    expect((await source.load('web')).groups.map((group) => group.title)).toEqual(['Browser', 'Approvals', 'Sites', 'Files', 'Privacy', 'Live view', 'Appearance', 'Advanced']);
    expect((await source.load('mobile')).groups.map((group) => group.title)).not.toContain('Advanced');
  });

  it('every setting says what it does, in one line under 110 characters', async () => {
    for (const setting of (await createDemoSettings().load('desktop')).groups.flatMap((group) => group.settings)) {
      expect(setting.description.length, setting.id).toBeGreaterThan(10);
      expect(setting.description.length, setting.id).toBeLessThanOrEqual(110);
      expect(setting.title.length, setting.id).toBeLessThanOrEqual(60);
    }
  });

  it('settings that start a new browser apply to the next session', async () => {
    const answer = await createDemoSettings().load('desktop');
    const next = answer.groups.flatMap((group) => group.settings).filter((setting) => setting.applies === 'next_session');
    expect(next.map((setting) => setting.id).sort()).toEqual(['preferred_browser', 'show_builtin_browser', 'stay_signed_in']);
  });
});

describe('changing settings', () => {
  it('a change is kept and returned', async () => {
    const source = createDemoSettings();
    const result = await source.change('web', { ask_before: 'every_action' });
    expect(result.ok).toBe(true);
    expect(find(await source.load('web'), 'ask_before').value).toBe('every_action');
  });

  it('a locked setting is refused and nothing changes', async () => {
    const source = createDemoSettings();
    expect(find(await source.load('web'), 'page_scripts').locked).toBe(true);
    expect(await source.change('web', { page_scripts: true, ask_before: 'every_action' })).toEqual({ ok: false, setting: 'page_scripts', reason: 'locked' });
    expect(find(await source.load('web'), 'ask_before').value).toBe('risky');
  });

  it('a setting from another surface is refused', async () => {
    expect(await createDemoSettings().change('mobile', { page_scripts: false })).toEqual({ ok: false, setting: 'page_scripts', reason: 'not_on_this_surface' });
  });

  it('a value that is not one of the choices is refused', async () => {
    expect(await createDemoSettings().change('web', { ask_before: 'never' })).toEqual({ ok: false, setting: 'ask_before', reason: 'not_a_choice' });
  });

  it.each(['not a site', 'http://example.com/path', 'exa mple.com', ''])('a list entry like %j is refused', async (entry) => {
    expect(await createDemoSettings().change('web', { blocked_sites: ['example.com', entry] })).toEqual({ ok: false, setting: 'blocked_sites', reason: 'bad_site' });
  });

  it('sites are accepted as names and as wildcards, and the deployment\'s entries stay', async () => {
    const source = createDemoSettings();
    const result = await source.change('web', { blocked_sites: ['ads.example.com', '*.tracker.example'] });
    expect(result.ok).toBe(true);
    const blocked = find(await source.load('web'), 'blocked_sites');
    expect(blocked.value).toEqual(['ads.example.com', '*.tracker.example']);
    expect(blocked.fixed).toEqual(['*.internal.example']);
  });

  it('each source keeps its own values', async () => {
    const one = createDemoSettings();
    await one.change('web', { colour_mode: 'dark' });
    expect(find(await createDemoSettings().load('web'), 'colour_mode').value).toBe('system');
  });
});

describe('actions and about', () => {
  it('clearing browsing data asks first, in words that say what is lost', async () => {
    const clear = find(await createDemoSettings().load('web'), 'clear_browsing_data');
    expect(clear.control).toBe('action');
    expect(clear.confirm).toEqual({
      question: 'Clear cookies and site data in the cloud browser?',
      consequence: "You'll be signed out of sites there, and open sessions will end.",
      button: 'Clear data',
    });
  });

  it('about lists what differs from the defaults, and no secret', async () => {
    const config = await createDemoSettings().config();
    expect(config.version).toMatch(/^\d+\.\d+\.\d+$/);
    expect(config.changed.length).toBeGreaterThan(0);
    expect(JSON.stringify(config)).not.toMatch(/token|password|secret/i);
  });
});
