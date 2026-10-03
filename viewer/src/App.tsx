// The viewer: one page that shows who is driving the browser, what is happening, and lets a person
// approve, pause, stop, take over and hand back (spec 9).

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';

import { BrowserPane } from './components/BrowserPane';
import { ApprovalCard, BlockedNotice, DialogCard, HelpCard, SummaryCard, UnwatchedNotice } from './components/Cards';
import { Icon } from './components/Icon';
import { SettingsScreen } from './components/SettingsScreen';
import { Button, Confirm, StatusPanel } from './components/StatusPanel';
import { StepDrawer, Timeline } from './components/Timeline';
import type { Connection } from './connection/connection';
import { DEFAULT_OPTIONS, type ViewerOptions } from './options';
import type { ClientCommand, Surface } from './protocol';
import { initialState, reduce, unseenNotices, type Notice } from './state/reducer';
import { formatSize } from './state/timeline';
import { describeState } from './state/view';
import type { SettingsAnswer, SettingsSource } from './settings/types';
import { W } from './wording';

export interface Preferences {
  colourMode: 'system' | 'light' | 'dark';
  showAgentPointer: boolean;
}

export const DEFAULT_PREFERENCES: Preferences = { colourMode: 'system', showAgentPointer: true };

/** The preferences the viewer itself acts on, read from the settings answer. */
export function preferencesFrom(answer: SettingsAnswer): Preferences {
  const value = (id: string) => answer.groups.flatMap((group) => group.settings).find((setting) => setting.id === id)?.value;
  const mode = value('colour_mode');
  return {
    colourMode: mode === 'light' || mode === 'dark' ? mode : 'system',
    showAgentPointer: value('show_agent_pointer') !== false,
  };
}

export interface AppProps {
  /** Opens the session's connection. Called once. */
  createConnection: () => Connection;
  settings: SettingsSource;
  surface?: Surface;
  /** Shown inside a UI client, which has its own header. */
  embedded?: boolean;
  options?: ViewerOptions;
  preferences?: Preferences;
}

interface Toast {
  key: string;
  text: string;
}

function toastFor(notice: Notice): Toast | null {
  const key = `notice-${notice.id}`;
  switch (notice.kind) {
    case 'approval':
      // Nobody saw that approval, so it stays on screen as a card until someone does.
      return notice.outcome === 'unwatched' ? null : { key, text: W.approval.outcome[notice.outcome] };
    case 'help':
      return { key, text: W.help.outcome[notice.outcome] };
    case 'download':
      return { key, text: W.notice.download(notice.name, formatSize(notice.size)) };
  }
}

export function App({ createConnection, settings, surface = 'web', embedded = false, options = DEFAULT_OPTIONS, preferences: given = DEFAULT_PREFERENCES }: AppProps) {
  const connection = useMemo(() => createConnection(), [createConnection]);
  const [state, dispatch] = useReducer(reduce, initialState);
  const [, setTick] = useState(0);
  const [wantsFull, setWantsFull] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmingStop, setConfirmingStop] = useState(false);
  const [preferences, setPreferences] = useState(given);
  const [ownToasts, setOwnToasts] = useState<Toast[]>([]);
  const [dismissed, setDismissed] = useState<ReadonlySet<string>>(new Set());

  const settingsButton = useRef<HTMLButtonElement>(null);
  const stopButton = useRef<HTMLButtonElement>(null);
  const primaryButton = useRef<HTMLButtonElement>(null);
  const approvalButton = useRef<HTMLButtonElement>(null);
  const helpCard = useRef<HTMLDivElement>(null);
  const rowBeforeDrawer = useRef<HTMLElement | null>(null);
  /** Where the focus goes once the settings screen has closed. */
  const afterSettings = useRef<'button' | 'pending' | null>(null);
  const toastCount = useRef(0);

  useEffect(() => {
    connection.start({
      onEvent: (event, picture) => dispatch({ type: 'event', event, picture }),
      onFrame: (src, at) => dispatch({ type: 'frame', src, at }),
      onStatus: (status) => dispatch({ type: 'connection', status }),
      onCaughtUp: () => dispatch({ type: 'caught_up' }),
    });
    return () => connection.close();
  }, [connection]);

  // The clock on screen: elapsed time, time left on a card, how long the picture has been still.
  useEffect(() => {
    if (!options.tickMs) return;
    const timer = setInterval(() => setTick((tick) => tick + 1), options.tickMs);
    return () => clearInterval(timer);
  }, [options.tickMs]);

  useEffect(() => {
    const root = document.documentElement;
    if (preferences.colourMode === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', preferences.colourMode);
    return () => root.removeAttribute('data-theme');
  }, [preferences.colourMode]);

  const now = connection.now();
  const view = describeState(state, now, options.staleAfterS);
  const driving = view.key === 'person';
  // A person who takes over gets the whole width to work in.
  const full = driving || wantsFull;
  const send = useCallback((command: ClientCommand) => connection.send(command), [connection]);

  const toast = useCallback((text: string) => {
    toastCount.current += 1;
    const key = `own-${toastCount.current}`;
    setOwnToasts((toasts) => [...toasts, { key, text }]);
  }, []);

  const toasts = useMemo(
    () =>
      [
        ...unseenNotices(state)
          .map(toastFor)
          .filter((item): item is Toast => item !== null),
        ...ownToasts,
      ].filter((item) => !dismissed.has(item.key)),
    [state, ownToasts, dismissed],
  );
  const dismiss = useCallback((key: string) => setDismissed((keys) => new Set(keys).add(key)), []);

  const newestToast = toasts.at(-1)?.key;
  useEffect(() => {
    if (!newestToast) return;
    const timer = setTimeout(() => dismiss(newestToast), options.toastMs);
    return () => clearTimeout(timer);
  }, [newestToast, dismiss, options.toastMs]);

  const unwatched = state.notices.find((notice) => notice.kind === 'approval' && notice.outcome === 'unwatched' && !dismissed.has(`notice-${notice.id}`));

  const focusPending = useCallback(() => {
    (approvalButton.current ?? helpCard.current)?.focus();
  }, []);

  useEffect(() => {
    if (settingsOpen || !afterSettings.current) return;
    if (afterSettings.current === 'pending') focusPending();
    else settingsButton.current?.focus();
    afterSettings.current = null;
  }, [settingsOpen, focusPending]);

  const closeSettings = useCallback((then: 'button' | 'pending') => {
    afterSettings.current = then;
    setSettingsOpen(false);
  }, []);

  const handBack = useCallback(() => {
    send({ type: 'hand_back' });
    toast(W.takeover.handedBack);
  }, [send, toast]);

  const openStep = useCallback((step: number) => {
    rowBeforeDrawer.current = document.activeElement as HTMLElement | null;
    setSelected(step);
  }, []);

  const closeStep = useCallback(() => {
    setSelected(null);
    rowBeforeDrawer.current?.focus();
  }, []);

  // The keyboard map (spec 9.8). Dialogs and the live picture during takeover keep their own keys.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey) return;
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest('input, textarea, select, [contenteditable="true"], [data-takes-keys="true"]')) return;
      const key = event.key.toLowerCase();
      if (key === 'a' && (state.approval || state.help)) {
        event.preventDefault();
        if (settingsOpen) closeSettings('pending');
        else focusPending();
        return;
      }
      if (settingsOpen || confirmingStop || selected !== null) return;
      if (key === 'p') {
        if (view.controls.includes('pause')) send({ type: 'pause' });
        else if (view.controls.includes('resume')) send({ type: 'resume' });
      } else if (key === 't' && (view.key === 'agent' || view.key === 'blocked')) {
        send({ type: 'take_over' });
      } else if (key === 'f' && !driving) {
        setWantsFull((value) => !value);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const assertive = state.approval
    ? W.announce.approval(state.approval.summary)
    : state.help && state.control === 'person_requested'
      ? W.announce.help(state.help.reason)
      : view.urgency === 'assertive'
        ? [view.status, view.detail].filter(Boolean).join('. ')
        : '';
  const polite = view.urgency === 'polite' ? (view.key === 'agent' && view.detail ? W.announce.newStep(view.detail) : view.status) : '';

  const status = (
    <StatusPanel
      view={view}
      now={now}
      layout={full ? 'bar' : 'card'}
      options={options}
      onCommand={send}
      onStop={() => setConfirmingStop(true)}
      onHandBack={handBack}
      primaryRef={primaryButton}
      stopRef={stopButton}
      onShowSplit={full && !driving ? () => setWantsFull(false) : undefined}
    />
  );
  const selectedStep = selected === null ? undefined : state.steps.find((step) => step.n === selected);

  return (
    <div className="app" data-view={full ? 'full' : 'split'} data-state={view.key} data-embedded={embedded}>
      <header className="top-bar">
        {embedded ? (
          <h1 className="sr-only">{W.topBar.embeddedTitle}</h1>
        ) : (
          <h1 className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">{W.product}</span>
          </h1>
        )}
        {state.session && (
          <>
            <span className="chip" data-kind="session" title={W.topBar.session}>
              <span className="chip-name">{W.topBar.session}</span>
              {state.session.id}
            </span>
            <span className="chip" data-kind="agent" title={W.topBar.agent}>
              <Icon name="agent" />
              <span className="chip-name sr-only">{W.topBar.agent}</span>
              {state.session.agent}
            </span>
            <span className="chip" data-kind="browser" title={state.session.browser}>
              <Icon name="globe" />
              <span className="chip-name sr-only">{W.topBar.browser}</span>
              {W.backend[state.session.backend]}
            </span>
          </>
        )}
        <span className="top-bar-space" />
        <span className="connection" data-status={state.connection}>
          <span className="connection-dot" aria-hidden="true" />
          {W.connection[state.connection]}
        </span>
        {!full && state.session && (
          <span className="wide-only">
            <Button kind="quiet" icon="expand" onClick={() => setWantsFull(true)} label={W.buttons.showFull}>
              {null}
            </Button>
          </span>
        )}
        <Button kind="quiet" icon="settings" onClick={() => setSettingsOpen(true)} ref={settingsButton} label={W.buttons.openSettings}>
          {null}
        </Button>
      </header>

      {full && (
        <section className="control-bar" aria-label={W.topBar.controls}>
          {status}
        </section>
      )}

      <main className="workspace">
        <BrowserPane
          state={state}
          view={view}
          now={now}
          showPointer={preferences.showAgentPointer}
          options={options}
          onCommand={send}
          onRelease={() => (primaryButton.current ?? stopButton.current)?.focus()}
        />
        {!full && (
          <section className="activity" aria-label="Activity">
            {status}
            {state.approval && (
              <ApprovalCard
                approval={state.approval}
                now={now}
                firstRef={approvalButton}
                onAnswer={(answer) => {
                  const id = state.approval?.id ?? '';
                  send(answer === 'deny' ? { type: 'deny', id } : { type: 'approve', id, scope: answer });
                }}
              />
            )}
            {state.help && <HelpCard help={state.help} now={now} cardRef={helpCard} />}
            {state.dialog && <DialogCard dialog={state.dialog} />}
            {view.key === 'blocked' && state.blocked && <BlockedNotice url={state.blocked.url} reason={state.blocked.reason} />}
            {unwatched && <UnwatchedNotice onDismiss={() => dismiss(`notice-${unwatched.id}`)} />}
            <SummaryCard state={state} />
            <Timeline state={state} now={now} options={options} selected={selected} onOpen={openStep} />
            {selectedStep && <StepDrawer step={selectedStep} viewport={state.session?.viewport ?? { width: 1280, height: 800 }} onClose={closeStep} />}
          </section>
        )}
      </main>

      <div className="toasts" role="status">
        {toasts.map((item) => (
          <div key={item.key} className="toast">
            <span>{item.text}</span>
            <Button kind="quiet" icon="close" onClick={() => dismiss(item.key)} label={W.buttons.dismiss}>
              {null}
            </Button>
          </div>
        ))}
      </div>

      {settingsOpen && (
        <SettingsScreen
          source={settings}
          surface={surface}
          version={state.settingsVersion}
          onClose={() => closeSettings('button')}
          onChanged={(answer) => setPreferences(preferencesFrom(answer))}
          onToast={toast}
        />
      )}

      {confirmingStop && (
        <Confirm
          question={W.stop.question}
          consequence={W.stop.consequence}
          confirm={W.buttons.stop}
          cancel={W.buttons.keepRunning}
          onConfirm={() => {
            setConfirmingStop(false);
            send({ type: 'stop' });
          }}
          onCancel={() => {
            setConfirmingStop(false);
            stopButton.current?.focus();
          }}
        />
      )}

      <div className="sr-only" aria-live="polite" data-testid="announce-polite">
        {polite}
      </div>
      <div className="sr-only" aria-live="assertive" data-testid="announce-assertive">
        {assertive}
      </div>
    </div>
  );
}
