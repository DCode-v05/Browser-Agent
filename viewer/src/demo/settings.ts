// The settings answer a deployment would give (spec 10.2), kept in memory. It stands in for the
// settings API until the service provides it, and follows the same rules: a locked setting is
// refused, a setting from another surface is refused, a list holds only sites.

import type { Surface } from '../protocol';
import type { ChangeResult, ConfigAnswer, RefusalReason, Setting, SettingsAnswer, SettingsSource, SettingValue } from '../settings/types';

type Entry = Omit<Setting, 'value'> & { group: string; surfaces: Surface[] };

const ALL: Surface[] = ['web', 'mobile', 'desktop'];
const NOT_MOBILE: Surface[] = ['web', 'desktop'];
const DESKTOP: Surface[] = ['desktop'];

const GROUPS = ['Browser', 'Approvals', 'Sites', 'Files', 'Privacy', 'Live view', 'Appearance', 'Advanced'];
const SITE = /^(\*\.)?[a-z0-9-]+(\.[a-z0-9-]+)+$/i;

const CATALOGUE: Entry[] = [
  {
    id: 'preferred_browser',
    group: 'Browser',
    surfaces: NOT_MOBILE,
    title: 'Preferred browser',
    description: 'The browser the agent uses for a new session.',
    control: 'choice',
    choices: [{ value: 'remote_headless', label: 'Cloud browser', hint: 'Runs beside the agent. You watch a live picture of it.' }],
    default: 'remote_headless',
    locked: false,
    applies: 'next_session',
  },
  {
    id: 'stay_signed_in',
    group: 'Browser',
    surfaces: ALL,
    title: 'Stay signed in to sites',
    description: 'Keeps the cloud browser\'s cookies and site data from one session to the next, so sites stay signed in.',
    control: 'switch',
    default: false,
    locked: false,
    applies: 'next_session',
  },
  {
    id: 'my_chrome',
    group: 'Browser',
    surfaces: DESKTOP,
    title: 'My Chrome',
    description: 'Not connected. Connect the extension to let the agent work in your own Chrome.',
    control: 'action',
    action: 'Connect',
    default: null,
    locked: false,
    applies: 'now',
  },
  {
    id: 'show_builtin_browser',
    group: 'Browser',
    surfaces: DESKTOP,
    title: 'Show the built-in browser',
    description: 'Whether the built-in browser is a visible pane or works out of sight.',
    control: 'choice',
    choices: [
      { value: 'shown', label: 'Shown' },
      { value: 'hidden', label: 'Hidden' },
    ],
    default: 'shown',
    locked: false,
    applies: 'next_session',
  },
  {
    id: 'ask_before',
    group: 'Approvals',
    surfaces: ALL,
    title: 'Ask before',
    description: 'When the agent must stop and wait for a person\'s approval before it acts.',
    control: 'choice',
    choices: [
      { value: 'risky', label: 'Risky actions', hint: 'Uploads, page scripts and whatever your organisation lists' },
      { value: 'every_action', label: 'Every action', hint: 'Each click, key press and page change' },
    ],
    default: 'risky',
    locked: false,
    applies: 'now',
  },
  {
    id: 'approval_wait',
    group: 'Approvals',
    surfaces: ALL,
    title: 'Wait for my answer',
    description: 'How long the agent waits for an answer to an approval. With no answer by then, the action is denied.',
    control: 'select',
    choices: [
      { value: '60', label: '1 minute' },
      { value: '180', label: '3 minutes' },
      { value: '300', label: '5 minutes' },
      { value: '600', label: '10 minutes' },
    ],
    default: '180',
    locked: false,
    applies: 'now',
  },
  {
    id: 'remember_site_approval',
    group: 'Approvals',
    surfaces: ALL,
    title: 'Remember "Allow on this site"',
    description: 'After "Allow on this site", how long the agent may go on acting on that site without asking again.',
    control: 'select',
    choices: [
      { value: 'session', label: 'Until the session ends' },
      { value: 'none', label: 'Never' },
    ],
    default: 'session',
    locked: false,
    applies: 'now',
  },
  {
    id: 'my_chrome_mode',
    group: 'Approvals',
    surfaces: DESKTOP,
    title: 'In my Chrome',
    description: 'How freely the agent acts in your own browser.',
    control: 'choice',
    choices: [
      { value: 'act_on_allowed_sites', label: "Act on sites I've allowed", hint: 'Buying, sending, deleting and uploading still ask' },
      { value: 'ask_before_acting', label: 'Ask before acting', hint: 'Every action shows a preview first' },
    ],
    default: 'act_on_allowed_sites',
    locked: false,
    applies: 'now',
  },
  {
    id: 'blocked_sites',
    group: 'Sites',
    surfaces: ALL,
    title: 'Blocked sites',
    description: 'Sites the agent must never open.',
    control: 'list',
    default: [],
    fixed: ['*.internal.example'],
    locked: false,
    applies: 'now',
  },
  {
    id: 'allowed_sites',
    group: 'Sites',
    surfaces: ALL,
    title: 'Only allow these sites',
    description: 'When this list has entries, the agent may open only these sites. Empty: any site that is not blocked.',
    control: 'list',
    default: [],
    locked: false,
    applies: 'now',
  },
  {
    id: 'approved_sites',
    group: 'Sites',
    surfaces: DESKTOP,
    title: 'Approved sites',
    description: 'Sites you chose "Always allow" for in your own browser. Kept on this computer.',
    control: 'list',
    default: ['github.com', 'mail.example.com'],
    locked: false,
    applies: 'now',
  },
  {
    id: 'allow_downloads',
    group: 'Files',
    surfaces: ALL,
    title: 'Let the agent download files',
    description: 'On: the agent may download files, saved where you can find them after the session. Off: it cannot.',
    control: 'switch',
    default: true,
    locked: false,
    applies: 'now',
  },
  {
    id: 'allow_uploads',
    group: 'Files',
    surfaces: ALL,
    title: 'Let the agent upload files',
    description: 'On: the agent may upload a file to a site; each upload still asks for approval. Off: it cannot.',
    control: 'switch',
    default: true,
    locked: false,
    applies: 'now',
  },
  {
    id: 'download_folder',
    group: 'Files',
    surfaces: DESKTOP,
    title: 'Download folder',
    description: 'Where files the agent downloads are saved on this computer.',
    control: 'path',
    action: 'Choose folder',
    default: 'Downloads/bap-browser',
    locked: false,
    applies: 'now',
  },
  {
    id: 'upload_folders',
    group: 'Files',
    surfaces: DESKTOP,
    title: 'Folders the agent may upload from',
    description: 'An upload may come only from these folders.',
    control: 'path',
    action: 'Add folder',
    default: 'Documents/bap-browser uploads',
    locked: false,
    applies: 'now',
  },
  {
    id: 'activity_log',
    group: 'Privacy',
    surfaces: ALL,
    title: "Keep a log of the agent's steps",
    description: 'Writes one line for each step the agent takes. What is typed is never logged, only its length.',
    control: 'switch',
    default: true,
    locked: false,
    applies: 'now',
  },
  {
    id: 'clear_browsing_data',
    group: 'Privacy',
    surfaces: ALL,
    title: 'Clear browsing data',
    description: 'Deletes cookies and site data in the cloud browser.',
    control: 'action',
    action: 'Clear data',
    confirm: {
      question: 'Clear cookies and site data in the cloud browser?',
      consequence: "You'll be signed out of sites there, and open sessions will end.",
      button: 'Clear data',
    },
    default: null,
    locked: false,
    applies: 'now',
  },
  {
    id: 'picture_quality',
    group: 'Live view',
    surfaces: ALL,
    title: 'Picture quality',
    description: 'How sharp the live picture of the browser is. A sharper picture uses more data.',
    control: 'choice',
    choices: [
      { value: 'standard', label: 'Standard' },
      { value: 'data_saver', label: 'Data saver', hint: 'For a slow or metered connection' },
      { value: 'high', label: 'High', hint: 'For a fast connection' },
    ],
    default: 'standard',
    locked: false,
    applies: 'now',
  },
  {
    id: 'show_agent_pointer',
    group: 'Live view',
    surfaces: ALL,
    title: 'Show where the agent is acting',
    description: "Outlines the element and shows the agent's pointer over the live picture.",
    control: 'switch',
    default: true,
    locked: false,
    applies: 'now',
  },
  {
    id: 'colour_mode',
    group: 'Appearance',
    surfaces: ALL,
    title: 'Colour mode',
    description: 'The colours of this window: light, dark, or the same as your device.',
    control: 'choice',
    choices: [
      { value: 'system', label: 'Match system' },
      { value: 'light', label: 'Light' },
      { value: 'dark', label: 'Dark' },
    ],
    default: 'system',
    locked: false,
    applies: 'now',
  },
  {
    id: 'page_scripts',
    group: 'Advanced',
    surfaces: NOT_MOBILE,
    title: 'Let the agent run scripts in pages',
    description: 'Offers the agent a tool that runs JavaScript in the page. Each use still asks.',
    control: 'switch',
    default: false,
    locked: true,
    applies: 'now',
  },
  {
    id: 'about',
    group: 'Advanced',
    surfaces: NOT_MOBILE,
    title: 'About this deployment',
    description: 'The version, the browser in use and the configuration that differs from the defaults.',
    control: 'about',
    default: null,
    locked: false,
    applies: 'now',
  },
];

/** The setting as the answer carries it: without the catalogue's own bookkeeping. */
function toSetting(entry: Entry, value: SettingValue): Setting {
  const setting: Setting & { group?: string; surfaces?: Surface[] } = { ...entry, value };
  delete setting.group;
  delete setting.surfaces;
  return setting;
}

function problemWith(entry: Entry | undefined, surface: Surface, value: SettingValue): RefusalReason | null {
  if (!entry || !entry.surfaces.includes(surface)) return 'not_on_this_surface';
  if (entry.locked) return 'locked';
  if (entry.control === 'list') {
    if (!Array.isArray(value) || !value.every((site) => SITE.test(site))) return 'bad_site';
    return null;
  }
  if (entry.control === 'switch') return typeof value === 'boolean' ? null : 'not_a_choice';
  if (entry.choices) return entry.choices.some((choice) => choice.value === value && !choice.disabled) ? null : 'not_a_choice';
  return 'not_a_choice';
}

/** `only` limits the catalogue to the settings named. */
export function createDemoSettings(only?: readonly string[]): SettingsSource {
  const catalogue = only ? CATALOGUE.filter((entry) => only.includes(entry.id)) : CATALOGUE;
  const values = new Map<string, SettingValue>(catalogue.map((entry) => [entry.id, entry.default]));

  function answer(surface: Surface): SettingsAnswer {
    const groups = GROUPS.map((title) => ({
      id: title.toLowerCase().replace(' ', '_'),
      title,
      settings: catalogue.filter((entry) => entry.group === title && entry.surfaces.includes(surface)).map((entry) =>
        toSetting(entry, values.get(entry.id) ?? null),
      ),
    }));
    return { surface, groups: groups.filter((group) => group.settings.length > 0) };
  }

  return {
    load: async (surface) => answer(surface),

    async change(surface, changes): Promise<ChangeResult> {
      // Nothing is changed when any one change in the request is refused.
      for (const [id, value] of Object.entries(changes)) {
        const reason = problemWith(catalogue.find((entry) => entry.id === id), surface, value);
        if (reason) return { ok: false, setting: id, reason };
      }
      for (const [id, value] of Object.entries(changes)) values.set(id, value);
      return { ok: true, answer: answer(surface) };
    },

    run: async () => undefined,

    config: async (): Promise<ConfigAnswer> => ({
      version: '0.1.0',
      browser: 'Chromium 153 (cloud browser)',
      changed: [
        { key: 'safety.blocked_domains', value: '["*.internal.example"]', source: 'config.json' },
        { key: 'safety.block_private_networks', value: 'true', source: 'config.json' },
        { key: 'settings.locked', value: '["page_scripts"]', source: 'config.json' },
        { key: 'server.public_url', value: '"https://vm-1234.example.app"', source: 'environment' },
      ],
    }),
  };
}
