// The viewer's icons: simple strokes on a 16 by 16 grid, coloured by the text around them.
// Every state has an icon and a label as well as a colour (spec 9.9).

const PATHS = {
  agent: 'M8 1.5v2M4.5 4.5h7a1.5 1.5 0 0 1 1.5 1.5v5a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 11V6a1.5 1.5 0 0 1 1.5-1.5ZM6 8v1M10 8v1M1.5 8v2M14.5 8v2',
  person: 'M8 8a2.75 2.75 0 1 0 0-5.5A2.75 2.75 0 0 0 8 8ZM2.75 13.5a5.25 5.25 0 0 1 10.5 0',
  pause: 'M5.5 3v10M10.5 3v10',
  play: 'M5 3.2v9.6a.4.4 0 0 0 .6.35l8-4.8a.4.4 0 0 0 0-.7l-8-4.8a.4.4 0 0 0-.6.35Z',
  stop: 'M4.5 3.5h7a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Z',
  hand: 'M5.5 7.5v-4a1 1 0 0 1 2 0v3.5M7.5 6.5v-4a1 1 0 0 1 2 0v4M9.5 7V4a1 1 0 0 1 2 0v5.5c0 2.5-1.5 4.5-4 4.5-2 0-3-1-4-3L2.4 9.2a1 1 0 0 1 1.7-1L5.5 10',
  approval: 'M8 1.75 2.75 3.75v4c0 3.1 2.1 5.4 5.25 6.5 3.15-1.1 5.25-3.4 5.25-6.5v-4L8 1.75ZM8 5.5v3M8 10.75v.01',
  help: 'M8 14.25a6.25 6.25 0 1 0 0-12.5 6.25 6.25 0 0 0 0 12.5ZM6.2 6.2a1.9 1.9 0 1 1 2.6 1.75c-.5.25-.8.6-.8 1.3M8 11.25v.01',
  dialog: 'M2.75 3.25h10.5a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H8l-3 2.5v-2.5H2.75a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1Z',
  blocked: 'M8 14.25a6.25 6.25 0 1 0 0-12.5 6.25 6.25 0 0 0 0 12.5ZM3.6 3.6l8.8 8.8',
  check: 'm3 8.5 3.2 3.2L13 4.8',
  close: 'm4 4 8 8M12 4l-8 8',
  clock: 'M8 14.25a6.25 6.25 0 1 0 0-12.5 6.25 6.25 0 0 0 0 12.5ZM8 4.75V8l2.25 1.5',
  globe: 'M8 14.25a6.25 6.25 0 1 0 0-12.5 6.25 6.25 0 0 0 0 12.5ZM1.9 8h12.2M8 1.75c1.7 1.7 2.5 3.8 2.5 6.25S9.7 12.55 8 14.25C6.3 12.55 5.5 10.45 5.5 8S6.3 3.45 8 1.75Z',
  lock: 'M4.25 7.25h7.5a1 1 0 0 1 1 1v4.5a1 1 0 0 1-1 1h-7.5a1 1 0 0 1-1-1v-4.5a1 1 0 0 1 1-1ZM5.5 7.25V5a2.5 2.5 0 0 1 5 0v2.25',
  settings: 'M2 4.5h6.5M11.5 4.5H14M2 11.5h2.5M7.5 11.5H14M10 6a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM6 13a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z',
  chevronDown: 'm4 6 4 4 4-4',
  chevronLeft: 'm10 4-4 4 4 4',
  chevronRight: 'm6 4 4 4-4 4',
  upload: 'M8 10.5v-8M4.75 5.5 8 2.25l3.25 3.25M2.75 10.5v2a1 1 0 0 0 1 1h8.5a1 1 0 0 0 1-1v-2',
  download: 'M8 2.5v8M4.75 7.5 8 10.75l3.25-3.25M2.75 10.5v2a1 1 0 0 0 1 1h8.5a1 1 0 0 0 1-1v-2',
  pointer: 'M3.5 2.5 12 7.6l-3.7.9-1.5 3.9L3.5 2.5Z',
  expand: 'M9.5 2.5h4v4M6.5 13.5h-4v-4M13.5 2.5 9 7M2.5 13.5 7 9',
  collapse: 'M13 7H9V3M3 9h4v4M9 7l4.5-4.5M7 9l-4.5 4.5',
  info: 'M8 14.25a6.25 6.25 0 1 0 0-12.5 6.25 6.25 0 0 0 0 12.5ZM8 7.25v3.5M8 5v.01',
  alert: 'M8 2.25 14.25 13H1.75L8 2.25ZM8 6.5v3M8 11.25v.01',
  copy: 'M5.75 5.75h7a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1ZM11.25 5.75v-2.5a1 1 0 0 0-1-1h-7a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1.5',
  monitor: 'M2.75 3h10.5a1 1 0 0 1 1 1v6.5a1 1 0 0 1-1 1H2.75a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM5.5 14h5M8 11.5V14',
  computer: 'M3.5 3.25h9a1 1 0 0 1 1 1v5.5h-11v-5.5a1 1 0 0 1 1-1ZM1.25 12.25h13.5M6.5 9.75v2.5M9.5 9.75v2.5',
  plug: 'M6 2v3M10 2v3M4.25 5h7.5v2.5a3.75 3.75 0 0 1-7.5 0V5ZM8 11.25V14',
  send: 'M8 13V3.5M3.75 7.5 8 3.25l4.25 4.25',
  file: 'M4.25 1.75h4.5l3 3v8.5a1 1 0 0 1-1 1h-6.5a1 1 0 0 1-1-1v-10.5a1 1 0 0 1 1-1ZM8.75 1.75v3h3',
} as const;

export type IconName = keyof typeof PATHS;

const FILLED = new Set<IconName>(['play', 'pointer']);

export function Icon({ name, size = 'regular' }: { name: IconName; size?: 'regular' | 'large' }) {
  const filled = FILLED.has(name);
  return (
    <svg className="icon" data-size={size} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        d={PATHS[name]}
        fill={filled ? 'currentColor' : 'none'}
        stroke="currentColor"
        strokeWidth={filled ? 1 : 1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
