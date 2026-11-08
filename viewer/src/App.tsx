import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';

import { BrowserPane } from './components/BrowserPane';
import { Conversation } from './components/Conversation';
import { agentStatus, ChatPanel } from './components/ChatPanel';
import { ApprovalCard, BlockedNotice, DialogCard, HelpCard, SummaryCard, UnwatchedNotice } from './components/Cards';
import { CheckBars, FlaggedNotice, ModeChip, TaskLine } from './components/AutoMode';
import { ApprovalPopup } from './components/ApprovalPopup';
import { HelpPopup } from './components/HelpPopup';
import { Icon } from './components/Icon';
import { SettingsScreen } from './components/SettingsScreen';
import { Button, Confirm, StatusPanel } from './components/StatusPanel';
import { StepDrawer, Timeline } from './components/Timeline';
import type { AppProps } from './AppProps';
export type { AppProps } from './AppProps';
import { DEFAULT_OPTIONS } from './options';
import type { ClientCommand } from './protocol';
import { initialState, reduce, unseenNotices } from './state/reducer';
import { lookOf, tellPanel, type Look } from './state/look';
import { describeState, type ControlName, type StateKey } from './state/view';
import { DEFAULT_PREFERENCES, preferencesFrom, type Preferences } from './preferences';
import { W } from './wording';
import { TheWords, wordsFor } from './words';
import { type Toast, toastFor } from './state/toasts';

const TAKES_A_MOMENT: Partial<Record<ClientCommand['type'], ControlName>> = { pause: 'pause', resume: 'resume', take_over: 'take_over', hand_back: 'hand_back' };

export function App({ createConnection, settings, surface = 'web', embedded = false, options = DEFAULT_OPTIONS, preferences: given = DEFAULT_PREFERENCES, onOpenSettings, inWindow = false, beside: chatAlone = false, where }: AppProps) {
  const hosted = onOpenSettings !== undefined;
  const Bar = inWindow ? 'div' : 'header';
  const Workspace = inWindow ? 'div' : 'main';
  const connection = useMemo(() => createConnection(), [createConnection]);
  const [state, dispatch] = useReducer(reduce, initialState);
  const L = wordsFor(state.session?.backend);
  useEffect(() => {
    if (!inWindow) document.title = L.product;
  }, [inWindow, L.product]);
  const [, setTick] = useState(0);
  const [wantsFull, setWantsFull] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [confirmingStop, setConfirmingStop] = useState(false);
  const [lookingFirst, setLookingFirst] = useState<string | null>(null);
  const [approvalLookedAt, setApprovalLookedAt] = useState<string | null>(null);
  const [own, setOwn] = useState<Preferences | null>(null);
  const preferences = hosted ? given : (own ?? given);
  const [ownToasts, setOwnToasts] = useState<Toast[]>([]);
  const [pressed, setPressed] = useState<{ name: ControlName; at: StateKey } | null>(null);
  const [dismissed, setDismissed] = useState<ReadonlySet<string>>(new Set());

  const openSettings = onOpenSettings ?? (() => setSettingsOpen(true));
  const settingsButton = useRef<HTMLButtonElement>(null);
  const stopButton = useRef<HTMLButtonElement>(null);
  const primaryButton = useRef<HTMLButtonElement>(null);
  const approvalButton = useRef<HTMLButtonElement>(null);
  const statusTitle = useRef<HTMLHeadingElement>(null);
  const helpCard = useRef<HTMLDivElement>(null);
  const rowBeforeDrawer = useRef<HTMLElement | null>(null);
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

  useEffect(() => {
    if (!options.tickMs) return;
    const timer = setInterval(() => setTick((tick) => tick + 1), options.tickMs);
    return () => clearInterval(timer);
  }, [options.tickMs]);

  useEffect(() => {
    if (hosted) return;
    const root = document.documentElement;
    if (preferences.colourMode === 'system') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', preferences.colourMode);
    return () => root.removeAttribute('data-theme');
  }, [hosted, preferences.colourMode]);

  const settingsVersion = state.settingsVersion;
  useEffect(() => {
    if (hosted || settingsVersion === 0) return;
    let current = true;
    settings.load(surface).then(
      (answer) => current && setOwn(preferencesFrom(answer)),
      () => undefined,
    );
    return () => {
      current = false;
    };
  }, [hosted, settings, surface, settingsVersion]);

  const started = state.task !== null || state.steps.length > 0 || state.ended !== null;
  const showBrowser = !state.session || started;

  const now = connection.now();
  const view = describeState(state, now, options.staleAfterS);
  const driving = view.key === 'person';
  const beside = chatAlone || state.session?.onScreen === true;
  const full = !beside && (driving || wantsFull);
  const talking = beside && state.chat.enabled;
  const look = beside && window.parent !== window ? JSON.stringify(lookOf(state, view, preferences.showAgentPointer)) : '';
  useEffect(() => {
    if (look) tellPanel(JSON.parse(look) as Look);
  }, [look, preferences.colourMode]);
  const viewKey = view.key;
  const send = useCallback(
    (command: ClientCommand) => {
      const control = TAKES_A_MOMENT[command.type];
      if (control) setPressed({ name: control, at: viewKey });
      connection.send(command);
    },
    [connection, viewKey],
  );
  const working = pressed && pressed.at === viewKey ? pressed.name : null;
  useEffect(() => {
    if (!pressed) return;
    const timer = setTimeout(() => setPressed(null), options.workingMs);
    return () => clearTimeout(timer);
  }, [pressed, options.workingMs]);

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
      } else if (key === 'f' && !driving && started) {
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

  const askingForHelp = state.help !== null && state.control === 'person_requested' && lookingFirst !== state.help.id && !settingsOpen && !confirmingStop;

  const askingToApprove = state.approval !== null && approvalLookedAt !== state.approval.id && !settingsOpen && !confirmingStop;
  const answerApproval = (answer: 'once' | 'site' | 'deny') => {
    const id = state.approval?.id ?? '';
    send(answer === 'deny' ? { type: 'deny', id } : { type: 'approve', id, scope: answer });
    statusTitle.current?.focus();
  };

  const status = (
    <StatusPanel
      view={askingForHelp ? { ...view, controls: view.controls.filter((control) => control === 'stop') } : view}
      now={now}
      layout={full ? 'bar' : 'card'}
      options={options}
      onCommand={send}
      onStop={() => setConfirmingStop(true)}
      onHandBack={handBack}
      primaryRef={primaryButton}
      stopRef={stopButton}
      onShowSplit={full && !driving ? () => setWantsFull(false) : undefined}
      titleRef={statusTitle}
      working={working}
    />
  );
  const blocked = view.key === 'blocked' ? state.blocked : null;
  const flaggedVisible = state.flagged.filter((item) => !dismissed.has(`flagged-${item.id}`));
  const autoPaused = state.auto?.state === 'paused';
  const needsAttention = Boolean(
    state.approval || state.help || state.dialog || blocked || unwatched || state.ended || flaggedVisible.length > 0 || autoPaused || state.limit || state.refused.length > 0,
  );
  const cards = (
    <>
      {state.approval && !askingToApprove && <ApprovalCard approval={state.approval} now={now} firstRef={approvalButton} onAnswer={answerApproval} />}
      {state.help && <HelpCard help={state.help} now={now} cardRef={helpCard} />}
      {state.dialog && <DialogCard dialog={state.dialog} />}
      {blocked && <BlockedNotice url={blocked.url} reason={blocked.reason} />}
      {flaggedVisible.map((item) => (
        <FlaggedNotice key={item.id} site={item.site} onClose={() => dismiss(`flagged-${item.id}`)} />
      ))}
      <CheckBars auto={state.auto} limit={state.limit} refused={state.refused} send={send} />
      {unwatched && <UnwatchedNotice onDismiss={() => dismiss(`notice-${unwatched.id}`)} />}
      <SummaryCard state={state} onNewSession={() => send({ type: 'new_session' })} />
    </>
  );
  const selectedStep = selected === null ? undefined : state.steps.find((step) => step.n === selected);

  return (
    <TheWords.Provider value={L}>
    <div className="app" data-view={full ? 'full' : 'split'} data-state={view.key} data-embedded={embedded} data-beside={beside || undefined}>
      {talking ? (
        <Conversation
          state={state}
          view={view}
          maxChars={options.maxTaskChars}
          embedded={embedded}
          selected={selected}
          cards={cards}
          drawer={selectedStep && <StepDrawer step={selectedStep} viewport={state.session?.viewport ?? { width: 1280, height: 800 }} onClose={closeStep} />}
          onCommand={send}
          onOpenStep={openStep}
          onHandBack={handBack}
          onStopSession={() => setConfirmingStop(true)}
          onOpenSettings={openSettings}
          titleRef={statusTitle}
          settingsRef={settingsButton}
          stopRef={stopButton}
          where={where}
        />
      ) : (
        <>
      <Bar className="top-bar">
        {inWindow ? null : embedded ? (
          <h1 className="sr-only">{L.topBar.embeddedTitle}</h1>
        ) : (
          <h1 className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <span className="brand-name">{L.product}</span>
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
              <Icon name={state.session.backend === 'contained_desktop' ? 'computer' : 'globe'} />
              <span className="chip-name sr-only">{L.topBar.browser}</span>
              {W.backend[state.session.backend]}
            </span>
            <ModeChip auto={state.auto} onClick={openSettings} />
          </>
        )}
        <span className="top-bar-space" />
        <span className="connection" data-status={state.connection}>
          <span className="connection-dot" aria-hidden="true" />
          {W.connection[state.connection]}
        </span>
        {!full && !beside && started && state.session && (
          <span className="wide-only">
            <Button kind="quiet" icon="expand" onClick={() => setWantsFull(true)} label={L.buttons.showFull}>
              {null}
            </Button>
          </span>
        )}
        <Button kind="quiet" icon="settings" onClick={openSettings} ref={settingsButton} label={W.buttons.openSettings}>
          {null}
        </Button>
      </Bar>
      <TaskLine task={state.task} onDrop={(host) => send({ type: 'drop_site', host })} />

      {full && (
        <section className="control-bar" aria-label={W.topBar.controls}>
          {status}
        </section>
      )}
      {full && needsAttention && (
        <section className="attention" aria-label={W.topBar.attention}>
          {cards}
        </section>
      )}

      <Workspace className="workspace" data-started={showBrowser || undefined}>
        {!beside && showBrowser && (
          <BrowserPane
            state={state}
            view={view}
            now={now}
            showPointer={preferences.showAgentPointer}
            options={options}
            onCommand={send}
            onRelease={() => (primaryButton.current ?? stopButton.current)?.focus()}
          />
        )}
        {!full && (
          <section className="activity" aria-label={W.parts.activity}>
            {status}
            {cards}
            {state.chat.enabled && (
              <ChatPanel
                chat={state.chat}
                status={agentStatus(view)}
                doing={view.working ? view.detail : ''}
                open={state.connection === 'connected' && !state.ended}
                maxChars={options.maxTaskChars}
                onSend={(text) => send({ type: 'task', text })}
              />
            )}
            {started && <Timeline state={state} now={now} options={options} selected={selected} onOpen={openStep} />}
            {selectedStep && <StepDrawer step={selectedStep} viewport={state.session?.viewport ?? { width: 1280, height: 800 }} onClose={closeStep} />}
          </section>
        )}
      </Workspace>
        </>
      )}

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
          onChanged={(answer) => setOwn(preferencesFrom(answer))}
          onToast={toast}
        />
      )}

      {askingForHelp && state.help && (
        <HelpPopup
          help={state.help}
          now={now}
          ownBrowser={beside}
          onTakeOver={() => send({ type: 'take_over' })}
          onCouldNot={() => send({ type: 'could_not' })}
          onLater={() => setLookingFirst(state.help?.id ?? null)}
        />
      )}

      {askingToApprove && state.approval && (
        <ApprovalPopup approval={state.approval} now={now} onAnswer={answerApproval} onLater={() => setApprovalLookedAt(state.approval?.id ?? null)} />
      )}

      {confirmingStop && (
        <Confirm
          question={W.stop.question}
          consequence={L.stop.consequence}
          confirm={W.buttons.stop}
          cancel={W.buttons.keepRunning}
          onConfirm={() => {
            setConfirmingStop(false);
            send({ type: 'stop' });
            statusTitle.current?.focus();
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
    </TheWords.Provider>
  );
}
