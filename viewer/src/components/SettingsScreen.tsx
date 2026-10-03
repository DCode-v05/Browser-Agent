// The settings screen (spec 9.12), drawn from the settings answer. A change is saved as soon as it
// is made; a locked setting is shown with its reason, never hidden.

import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

import type { Surface } from '../protocol';
import type { ConfigAnswer, Setting, SettingsAnswer, SettingsSource, SettingValue } from '../settings/types';
import { W } from '../wording';
import { Icon } from './Icon';
import { Button, Confirm } from './StatusPanel';
import { trapTab } from './focus';

interface Props {
  source: SettingsSource;
  surface: Surface;
  /** Goes up when the settings changed elsewhere, so they are read again. */
  version: number;
  onClose(): void;
  onChanged(answer: SettingsAnswer): void;
  onToast(text: string): void;
}

type RowStatus = { id: string; tone: 'saved' | 'refused'; text: string };

export function SettingsScreen({ source, surface, version, onClose, onChanged, onToast }: Props) {
  const [answer, setAnswer] = useState<SettingsAnswer | null>(null);
  const [failed, setFailed] = useState(false);
  const [groupId, setGroupId] = useState<string | null>(null);
  /** Below 700 px the groups and one group's settings take turns on screen. */
  const [pane, setPane] = useState<'groups' | 'settings'>('groups');
  const [status, setStatus] = useState<RowStatus | null>(null);
  const [asking, setAsking] = useState<Setting | null>(null);
  const dialog = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let current = true;
    source.load(surface).then(
      (loaded) => current && setAnswer(loaded),
      () => current && setFailed(true),
    );
    return () => {
      current = false;
    };
  }, [source, surface, version]);

  const group = answer?.groups.find((item) => item.id === groupId) ?? answer?.groups[0];
  const loaded = answer !== null;

  // Focus goes to the chosen group once the settings have arrived.
  useEffect(() => {
    if (loaded) dialog.current?.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
  }, [loaded]);

  async function save(setting: Setting, value: SettingValue) {
    const result = await source.change(surface, { [setting.id]: value });
    if (result.ok) {
      setAnswer(result.answer);
      onChanged(result.answer);
      setStatus({ id: setting.id, tone: 'saved', text: setting.applies === 'next_session' ? W.settings.savedNext : W.settings.saved });
    } else {
      setStatus({ id: setting.id, tone: 'refused', text: W.settings.refused[result.reason] });
    }
    return result.ok;
  }

  async function run(setting: Setting) {
    setAsking(null);
    await source.run(surface, setting.id);
    if (setting.id === 'clear_browsing_data') onToast(W.settings.clear.done);
  }

  const moveTab = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!answer || (event.key !== 'ArrowDown' && event.key !== 'ArrowUp')) return;
    event.preventDefault();
    const index = answer.groups.findIndex((item) => item.id === group?.id);
    const next = answer.groups[(index + (event.key === 'ArrowDown' ? 1 : -1) + answer.groups.length) % answer.groups.length];
    setGroupId(next.id);
    setStatus(null);
    event.currentTarget.querySelector<HTMLElement>(`[data-group="${next.id}"]`)?.focus();
  };

  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div
        className="settings"
        role="dialog"
        aria-modal="true"
        aria-label={W.settings.title}
        data-pane={pane}
        ref={dialog}
        onKeyDown={(event) => {
          if (event.key === 'Escape' && !asking) {
            event.stopPropagation();
            onClose();
          }
          trapTab(event);
        }}
      >
        <div className="settings-head">
          <h2 className="settings-title">{W.settings.title}</h2>
          <Button kind="quiet" icon="close" onClick={onClose} label={W.buttons.close}>
            {null}
          </Button>
        </div>
        {failed && <p className="settings-message">{W.settings.failed}</p>}
        {!answer && !failed && <p className="settings-message">{W.settings.loading}</p>}
        {answer && group && (
          <div className="settings-body">
            <div className="settings-groups" role="tablist" aria-label={W.settings.groups} aria-orientation="vertical" onKeyDown={moveTab}>
              {answer.groups.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  className="settings-group"
                  id={`settings-tab-${item.id}`}
                  data-group={item.id}
                  aria-selected={item.id === group.id}
                  aria-controls="settings-panel"
                  tabIndex={item.id === group.id ? 0 : -1}
                  onClick={() => {
                    setGroupId(item.id);
                    setPane('settings');
                    setStatus(null);
                  }}
                >
                  {item.title}
                  <Icon name="chevronRight" />
                </button>
              ))}
            </div>
            <div className="settings-panel" role="tabpanel" id="settings-panel" aria-labelledby={`settings-tab-${group.id}`}>
              <div className="settings-panel-head">
                <Button kind="quiet" icon="chevronLeft" onClick={() => setPane('groups')}>
                  {W.buttons.back}
                </Button>
                <h3 className="settings-group-title">{group.title}</h3>
              </div>
              {group.settings.map((setting) => (
                <SettingRow
                  key={setting.id}
                  setting={setting}
                  status={status?.id === setting.id ? status : null}
                  source={source}
                  onSave={(value) => save(setting, value)}
                  onAct={() => (setting.confirm ? setAsking(setting) : run(setting))}
                  onToast={onToast}
                />
              ))}
            </div>
          </div>
        )}
      </div>
      {asking?.confirm && (
        <Confirm
          question={asking.confirm.question}
          consequence={asking.confirm.consequence}
          confirm={asking.confirm.button}
          cancel={W.buttons.cancel}
          onConfirm={() => run(asking)}
          onCancel={() => setAsking(null)}
        />
      )}
    </div>
  );
}

interface RowProps {
  setting: Setting;
  status: RowStatus | null;
  source: SettingsSource;
  onSave(value: SettingValue): Promise<boolean>;
  onAct(): void;
  onToast(text: string): void;
}

function SettingRow({ setting, status, source, onSave, onAct, onToast }: RowProps) {
  const titleId = useId();
  const descriptionId = useId();
  const footer = (
    <>
      {setting.locked && (
        <p className="setting-locked">
          <Icon name="lock" />
          {W.settings.locked}
        </p>
      )}
      {status && (
        <p className="setting-status" data-tone={status.tone} role="status">
          {status.tone === 'saved' && <Icon name="check" />}
          {status.text}
        </p>
      )}
    </>
  );

  if (setting.control === 'choice') {
    return (
      <fieldset className="setting" disabled={setting.locked}>
        <legend className="setting-title">{setting.title}</legend>
        <p className="setting-description">{setting.description}</p>
        <div className="choices">
          {setting.choices?.map((choice) => (
            <label key={choice.value} className="choice" data-disabled={choice.disabled || setting.locked}>
              <input
                type="radio"
                name={setting.id}
                value={choice.value}
                checked={setting.value === choice.value}
                disabled={choice.disabled}
                onChange={() => onSave(choice.value)}
              />
              <span className="choice-text">
                <span className="choice-label">{choice.label}</span>
                {choice.hint && <span className="choice-hint">{choice.hint}</span>}
                {choice.disabled && <span className="choice-hint">{W.settings.locked}</span>}
              </span>
            </label>
          ))}
        </div>
        {footer}
      </fieldset>
    );
  }

  if (setting.control === 'about') {
    return <About setting={setting} source={source} onToast={onToast} />;
  }

  return (
    <div className="setting" data-control={setting.control}>
      <div className="setting-line">
        <div className="setting-words">
          <p className="setting-title" id={titleId}>
            {setting.title}
          </p>
          <p className="setting-description" id={descriptionId}>
            {setting.description}
          </p>
        </div>
        {setting.control === 'switch' && (
          <button
            type="button"
            role="switch"
            className="switch"
            aria-checked={setting.value === true}
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            disabled={setting.locked}
            onClick={() => onSave(setting.value !== true)}
          >
            <span className="switch-knob" aria-hidden="true" />
            <span className="switch-word" aria-hidden="true">
              {setting.value === true ? W.settings.on : W.settings.off}
            </span>
          </button>
        )}
        {setting.control === 'select' && (
          <select
            className="select"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            value={String(setting.value)}
            disabled={setting.locked}
            onChange={(event) => onSave(event.target.value)}
          >
            {setting.choices?.map((choice) => (
              <option key={choice.value} value={choice.value} disabled={choice.disabled}>
                {choice.label}
              </option>
            ))}
          </select>
        )}
        {(setting.control === 'action' || setting.control === 'path') && (
          <Button kind={setting.confirm ? 'danger' : 'plain'} onClick={onAct} disabled={setting.locked}>
            {setting.action}
          </Button>
        )}
      </div>
      {setting.control === 'path' && typeof setting.value === 'string' && <p className="setting-path">{setting.value}</p>}
      {setting.control === 'list' && <SiteList setting={setting} labelledBy={titleId} onSave={onSave} />}
      {footer}
    </div>
  );
}

function SiteList({ setting, labelledBy, onSave }: { setting: Setting; labelledBy: string; onSave(value: SettingValue): Promise<boolean> }) {
  const saved = Array.isArray(setting.value) ? setting.value.join('\n') : '';
  const [text, setText] = useState(saved);
  const hintId = useId();
  return (
    <div className="site-list">
      {setting.fixed && setting.fixed.length > 0 && (
        <ul className="fixed-sites" aria-label={W.settings.locked}>
          {setting.fixed.map((site) => (
            <li key={site} className="fixed-site">
              <Icon name="lock" />
              <span>{site}</span>
            </li>
          ))}
        </ul>
      )}
      <textarea
        className="sites"
        rows={3}
        spellCheck={false}
        aria-labelledby={labelledBy}
        aria-describedby={hintId}
        value={text}
        disabled={setting.locked}
        onChange={(event) => setText(event.target.value)}
        // What was typed stays in the box when it is refused, so it can be corrected.
        onBlur={() => {
          if (text !== saved) void onSave(text.split('\n').map((line) => line.trim()).filter(Boolean));
        }}
      />
      <p className="setting-hint" id={hintId}>
        {W.settings.listHint}
      </p>
    </div>
  );
}

function About({ setting, source, onToast }: { setting: Setting; source: SettingsSource; onToast(text: string): void }) {
  const [config, setConfig] = useState<ConfigAnswer | null>(null);
  useEffect(() => {
    let current = true;
    source.config().then((loaded) => current && setConfig(loaded));
    return () => {
      current = false;
    };
  }, [source]);

  const asText = config
    ? [`${W.settings.about.version}: ${config.version}`, `${W.settings.about.browser}: ${config.browser}`, ...config.changed.map((item) => `${item.key} = ${item.value} (${item.source})`)].join('\n')
    : '';

  return (
    <div className="setting about">
      <p className="setting-title">{setting.title}</p>
      <p className="setting-description">{setting.description}</p>
      {config && (
        <>
          <dl className="facts">
            <div className="fact">
              <dt>{W.settings.about.version}</dt>
              <dd>{config.version}</dd>
            </div>
            <div className="fact">
              <dt>{W.settings.about.browser}</dt>
              <dd>{config.browser}</dd>
            </div>
          </dl>
          <p className="drawer-label">{W.settings.about.changed}</p>
          {config.changed.length === 0 ? (
            <p className="setting-hint">{W.settings.about.nothingChanged}</p>
          ) : (
            <ul className="config-list">
              {config.changed.map((item) => (
                <li key={item.key} className="config-item">
                  <span className="config-key">{item.key}</span>
                  <span className="config-value">{item.value}</span>
                  <span className="config-source">
                    {W.settings.about.from} {item.source}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <Button
            icon="copy"
            onClick={() => {
              void navigator.clipboard?.writeText(asText);
              onToast(W.settings.about.copied);
            }}
          >
            {W.buttons.copy}
          </Button>
        </>
      )}
    </div>
  );
}
