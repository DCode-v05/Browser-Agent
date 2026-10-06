// The browser column: tabs, address, and the live picture with who is driving on its border.

import { useEffect, useRef, type CSSProperties, type KeyboardEvent, type PointerEvent, type WheelEvent } from 'react';

import { matchesChord, type ViewerOptions } from '../options';
import type { Box, ClientCommand } from '../protocol';
import type { Step, ViewerState } from '../state/reducer';
import type { StateView, Tone } from '../state/view';
import { W } from '../wording';
import { Icon, type IconName } from './Icon';

const TONE_ICON: Record<Tone, IconName> = {
  none: 'monitor',
  agent: 'agent',
  person: 'person',
  waiting: 'clock',
  neutral: 'pause',
  danger: 'blocked',
};

interface Props {
  state: ViewerState;
  view: StateView;
  now: number;
  showPointer: boolean;
  options: ViewerOptions;
  onCommand(command: ClientCommand): void;
  /** The release chord was pressed while a person drives. */
  onRelease(): void;
}

export function BrowserPane({ state, view, now, showPointer, options, onCommand, onRelease }: Props) {
  return (
    <section className="browser" aria-label="Browser">
      {state.session && state.tabs.length > 0 && (
        <div className="tabs" role="tablist" aria-label="Browser tabs">
          {state.tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              className="tab"
              aria-selected={tab.active}
              onClick={() => onCommand({ type: 'select_tab', id: tab.id })}
            >
              <span className="tab-title">{tab.title || tab.url}</span>
              {tab.attention && <span className="tab-attention" aria-label="needs attention" />}
            </button>
          ))}
        </div>
      )}
      {state.session && <AddressBar state={state} view={view} now={now} />}
      <div className="frame-area">
        <LiveFrame state={state} view={view} showPointer={showPointer} options={options} onCommand={onCommand} onRelease={onRelease} />
      </div>
    </section>
  );
}

function AddressBar({ state, view, now }: { state: ViewerState; view: StateView; now: number }) {
  const url = state.url || 'about:blank';
  const blocked = view.key === 'blocked';
  return (
    <div className="address" data-blocked={blocked}>
      <Icon name={blocked ? 'blocked' : url.startsWith('https://') ? 'lock' : 'globe'} />
      <div className="address-url" role="group" aria-label="Address">
        {blocked && state.blocked ? state.blocked.url : url}
      </div>
      <FrameBadge state={state} view={view} now={now} />
    </div>
  );
}

function FrameBadge({ state, view, now }: { state: ViewerState; view: StateView; now: number }) {
  switch (view.frame) {
    case 'live':
    case 'person':
    case 'paused':
      return (
        <span className="badge" data-kind="live">
          <span className="live-dot" aria-hidden="true" />
          {W.frame.live}
        </span>
      );
    case 'stale':
      return (
        <span className="badge" data-kind="stale">
          <Icon name="clock" />
          {W.frame.stale(Math.floor(now - (state.frame?.at ?? now)))}
        </span>
      );
    case 'connecting':
      return <span className="badge">{W.frame.connecting}</span>;
    case 'disconnected':
      return (
        <span className="badge" data-kind="stale">
          {W.frame.notLive}
        </span>
      );
    default:
      return null;
  }
}

/** The tools that press a mouse button. */
const CLICKS = new Set(['browser_click']);

/** The element the agent acted on most recently. A step on something off screen has none. */
function lastTarget(steps: readonly Step[]): Box | undefined {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const target = steps[index]?.target;
    if (target) return target;
  }
  return undefined;
}

function centre(box: Box | undefined): { x: number; y: number } | undefined {
  return box && { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

type FrameProps = Omit<Props, 'now'>;

function LiveFrame({ state, view, showPointer, options, onCommand, onRelease }: FrameProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  /** The keys the person is holding down in the page: where each is on the keyboard, and its name. */
  const held = useRef(new Map<string, string>());
  const size = state.session?.viewport ?? { width: 1280, height: 800 };
  const src = state.frame?.src;
  const driving = view.key === 'person';

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext('2d');
    if (!canvas || !context || !src) return;
    let current = true;
    const image = new Image();
    image.onload = () => {
      if (current) context.drawImage(image, 0, 0, canvas.width, canvas.height);
    };
    image.src = src;
    return () => {
      current = false;
    };
  }, [src]);

  if (view.frame === 'empty' || view.frame === 'own_browser') {
    const own = view.frame === 'own_browser';
    const refused = view.key === 'refused';
    return (
      <div className="frame frame-placeholder" data-tone={own ? view.tone : 'none'}>
        <Icon name={own ? 'globe' : 'monitor'} size="large" />
        <p className="placeholder-title">{own ? W.frame.ownBrowser : refused ? W.frame.noSession : W.frame.waitingForAgent}</p>
        {!own && !refused && <p className="placeholder-hint">{W.frame.waitingForAgentHint}</p>}
        {own && view.label && <FrameLabel tone={view.tone} label={view.label} />}
      </div>
    );
  }

  /** Where the pointer is, in page pixels. */
  const pagePoint = (event: PointerEvent<HTMLCanvasElement> | WheelEvent<HTMLCanvasElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const scaleX = rect.width ? size.width / rect.width : 1;
    const scaleY = rect.height ? size.height / rect.height : 1;
    return { x: Math.round((event.clientX - rect.left) * scaleX), y: Math.round((event.clientY - rect.top) * scaleY) };
  };
  const pointer = (action: 'move' | 'down' | 'up') => (event: PointerEvent<HTMLCanvasElement>) => {
    onCommand({ type: 'pointer', action, button: event.button, ...pagePoint(event) });
  };
  const key = (action: 'down' | 'up', event: KeyboardEvent<HTMLCanvasElement>) => {
    event.stopPropagation();
    if (matchesChord(event, options.releaseChord)) {
      event.preventDefault();
      if (action === 'down') onRelease();
      return;
    }
    // Tab still moves focus, so a person is never stuck in the picture.
    if (event.key === 'Tab') return;
    event.preventDefault();
    if (action === 'down') held.current.set(event.code, event.key);
    else held.current.delete(event.code);
    onCommand({ type: 'key', action, key: event.key, code: event.code });
  };
  // A key that comes up while the picture does not have the focus is never seen here, and would
  // stay down in the page.
  const letGo = () => {
    for (const [code, name] of held.current) onCommand({ type: 'key', action: 'up', key: name, code });
    held.current.clear();
  };
  const wheel = (event: WheelEvent<HTMLCanvasElement>) => {
    onCommand({ type: 'wheel', dx: event.deltaX, dy: event.deltaY, ...pagePoint(event) });
  };

  const last = state.steps.at(-1);
  const acting = view.key === 'agent' || view.key === 'paused' || view.key === 'waiting_approval';
  const shown = showPointer && acting;
  // The outline is on the element while the step runs, and stays a moment after it has finished.
  const target = shown ? last?.target : undefined;
  const acted = last?.status !== 'running';
  // The agent's pointer stays where it last acted and moves from there to the next target.
  const at = shown ? centre(lastTarget(state.steps)) : undefined;
  const clicked = Boolean(target) && acted && last?.status === 'ok' && CLICKS.has(last.tool);
  const active = state.tabs.find((tab) => tab.active);
  const dimmed = view.frame === 'ended' || view.frame === 'disconnected' || view.frame === 'connecting';

  return (
    <div className="frame" data-tone={view.tone} data-frame={view.frame} data-working={(view.working && view.frame === 'live') || undefined} style={{ '--frame-w': size.width, '--frame-h': size.height, '--pointer-hold': `${options.pointerHoldMs}ms` } as CSSProperties}>
      <canvas
        ref={canvasRef}
        className="frame-picture"
        width={size.width}
        height={size.height}
        role="img"
        aria-label={W.frame.alt(active?.title ?? '', state.url)}
        tabIndex={driving ? 0 : -1}
        data-takes-keys={driving}
        {...(driving
          ? {
              onPointerDown: pointer('down'),
              onPointerMove: pointer('move'),
              onPointerUp: pointer('up'),
              onWheel: wheel,
              onKeyDown: (event: KeyboardEvent<HTMLCanvasElement>) => key('down', event),
              onKeyUp: (event: KeyboardEvent<HTMLCanvasElement>) => key('up', event),
              onBlur: letGo,
            }
          : {})}
      />
      {target && last && (
        <span
          // A new step draws a new outline, so its fade starts again.
          key={`target-${last.n}-${last.status}`}
          className="target"
          data-tone={view.tone}
          data-state={acted ? (last.status === 'failed' ? 'failed' : 'acted') : 'targeting'}
          aria-hidden="true"
          style={{
            left: `${(target.x / size.width) * 100}%`,
            top: `${(target.y / size.height) * 100}%`,
            width: `${(target.w / size.width) * 100}%`,
            height: `${(target.h / size.height) * 100}%`,
          }}
        />
      )}
      {clicked && at && last && (
        <span key={`click-${last.n}`} className="click-mark" data-tone={view.tone} aria-hidden="true" style={{ left: `${(at.x / size.width) * 100}%`, top: `${(at.y / size.height) * 100}%` }}>
          <span className="click-ring" />
        </span>
      )}
      {at && (
        <span
          className="agent-pointer"
          data-tone={view.tone}
          aria-hidden="true"
          // Moved with a transform, so the pointer glides from where it was (spec 9.10).
          style={{ transform: `translate(${(at.x / size.width) * 100}%, ${(at.y / size.height) * 100}%)` }}
        >
          <Icon name="pointer" size="large" />
        </span>
      )}
      {view.working && view.frame === 'live' && <span className="frame-glow" aria-hidden="true" />}
      {dimmed && <div className="frame-veil">{view.frame === 'connecting' && <span>{W.frame.connecting}</span>}</div>}
      {/* An agent that waits for a task is not paused: it keeps its own mark. */}
      {view.label && <FrameLabel tone={view.tone} label={view.label} icon={view.key === 'agent' ? 'agent' : undefined} />}
      {driving && <p className="frame-hint">{W.takeover.release(options.releaseChord)}</p>}
    </div>
  );
}

function FrameLabel({ tone, label, icon }: { tone: Tone; label: string; icon?: IconName }) {
  return (
    <div className="frame-label" data-tone={tone}>
      <Icon name={icon ?? TONE_ICON[tone]} />
      {label}
    </div>
  );
}
