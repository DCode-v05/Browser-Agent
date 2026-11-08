import type { ReactNode } from 'react';

import { Icon, type IconName } from '../components/Icon';
import { PAGE } from '../options';
import type { Backend } from '../protocol';
import { W } from '../wording';
import type { LogAnswer, SystemInfo } from './api';
import { clock, spanOf } from './format';

export const BACKEND_ICON: Record<Backend, IconName> = {
  remote_headless: 'globe',
  takeover_chrome: 'person',
  bundled_chromium: 'monitor',
  contained_desktop: 'computer',
};
export const NOT_RUNNING = new Set(['starting', 'waiting', 'failed', 'off', 'ended']);

export function CardHead({ system, word }: { system: SystemInfo; word: string }) {
  return (
    <header className="system-head">
      <Icon name={BACKEND_ICON[system.backend]} size="large" />
      <h3 className="system-name">{W.backend[system.backend]}</h3>
      <span className="system-state" data-on={system.enabled && !NOT_RUNNING.has(system.state)}>
        <span className="studio-tab-dot" aria-hidden="true" />
        {word}
      </span>
    </header>
  );
}

export function Switch({ label, on, locked, onChange }: { label: string; on: boolean; locked?: boolean; onChange(next: boolean): void }) {
  return (
    <button type="button" role="switch" className="switch" aria-checked={on} aria-label={label} disabled={locked} onClick={() => onChange(!on)}>
      <span className="switch-knob" aria-hidden="true" />
      <span className="switch-word" aria-hidden="true">
        {on ? W.settings.on : W.settings.off}
      </span>
    </button>
  );
}

export function TableScroll({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="system-table-scroll" role="group" aria-label={label} tabIndex={0}>
      {children}
    </div>
  );
}

export function SwitchRow({ title, description, label, on, onChange }: { title: string; description: string; label: string; on: boolean; onChange(next: boolean): void }) {
  return (
    <div className="system-row">
      <span className="system-row-name">
        {title}
        <span className="system-row-hint">{description}</span>
      </span>
      <Switch label={label} on={on} onChange={onChange} />
    </div>
  );
}

export function LogLines({ log }: { log: LogAnswer }) {
  const lines = log.lines.slice(-PAGE.logLinesShown).reverse();
  if (lines.length === 0) return <p className="system-note">{W.systems.logEmpty}</p>;
  return (
    <div className="system-log">
      <p className="system-note">{W.systems.logNewest(lines.length)}</p>
      <ol className="system-log-lines">
        {lines.map((line, index) => (
          <li key={`${line.ts}-${index}`} className="system-log-line" data-ok={line.ok}>
            <span className="system-log-when">{clock(line.ts)}</span>
            <span className="system-log-tool">{line.tool.replace('browser_', '')}</span>
            <span className="system-log-took">
              {line.ok ? W.systems.worked : W.systems.didNot}, {spanOf(line.ms)}
            </span>
            <span className="system-log-said">{line.result}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
