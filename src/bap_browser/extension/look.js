// Shows, on the page itself, who is driving the browser: a glowing edge, a label, and the agent's
// pointer on what it is acting on. What to show comes from the session's viewer through the side
// panel (panel.js); this script decides nothing and holds no words of its own.
//
// Everything is drawn inside a closed shadow root on one element that takes no clicks, so the page
// and the agent's reading of the page see none of it.

(() => {
  const LOOK = 'bap-browser.look';
  // With no word from the side panel for this long, the page shows nothing: the panel was closed or
  // the session ended.
  const FORGET_MS = 3000;
  const TONES = ['agent', 'person', 'waiting', 'neutral', 'danger'];

  const STYLE = `
    :host { all: initial; position: fixed; inset: 0; z-index: 2147483647; pointer-events: none; }
    * { box-sizing: border-box; }
    .edge { position: fixed; inset: 0; border: 3px solid var(--tone); opacity: 0;
      box-shadow: inset 0 0 28px 2px color-mix(in srgb, var(--tone) 55%, transparent); transition: opacity 200ms ease-out; }
    .pill { position: fixed; left: 16px; bottom: 16px; display: inline-flex; align-items: center; gap: 8px;
      max-width: min(70vw, 560px); padding: 7px 14px; border-radius: 999px; background: var(--tone); color: var(--on-tone);
      font: 500 13px/1.3 system-ui, "Segoe UI", Roboto, sans-serif; box-shadow: 0 4px 20px rgb(0 0 0 / 0.18);
      opacity: 0; transform: translateY(4px); transition: opacity 200ms ease-out, transform 200ms ease-out; }
    .dot { flex: none; width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
    .label { flex: none; }
    .detail { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; opacity: 0.85; font-weight: 400; }
    .target { position: fixed; border-radius: 4px; outline: 2px solid var(--tone); outline-offset: 4px;
      background: color-mix(in srgb, var(--tone) 14%, transparent); opacity: 0; transition: opacity 200ms ease-out; }
    .pointer { position: fixed; left: 0; top: 0; width: 22px; height: 22px; color: var(--tone); opacity: 0;
      filter: drop-shadow(0 1px 1px rgb(255 255 255 / 0.9)); transition: transform 350ms cubic-bezier(0.22, 1, 0.36, 1), opacity 200ms ease-out; }
    .ring { position: fixed; left: 0; top: 0; width: 36px; height: 36px; margin: -18px 0 0 -18px; border-radius: 50%;
      border: 2px solid var(--tone); opacity: 0; }
    .ring.go { animation: ring 600ms ease-out; }
    :host([data-tone]) .edge, :host([data-tone]) .pill { opacity: 1; transform: none; }
    :host([data-working]) .edge { animation: breathe 2s ease-in-out infinite alternate; }
    :host([data-working]) .dot { animation: breathe 1s ease-in-out infinite alternate; }
    .target.on, .pointer.on { opacity: 1; }
    @keyframes breathe { from { opacity: 0.55; } to { opacity: 1; } }
    @keyframes ring { from { opacity: 1; transform: scale(0.4); } to { opacity: 0; transform: scale(1.4); } }
    @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
  `;
  const SVG = 'http://www.w3.org/2000/svg';
  const POINTER_SHAPE = 'M4 2.5l15 8.2-6.6 1.7-1.7 6.6z';

  let host = null;
  let parts = null;
  let forget = 0;
  let lastClick = null;

  function build() {
    host = document.createElement('bap-browser-look');
    host.setAttribute('aria-hidden', 'true');
    const root = host.attachShadow({ mode: 'closed' });
    const style = document.createElement('style');
    style.textContent = STYLE;
    const make = (name) => {
      const element = document.createElement('div');
      element.className = name;
      return element;
    };
    parts = { edge: make('edge'), target: make('target'), pointer: make('pointer'), ring: make('ring'), pill: make('pill') };
    const arrow = document.createElementNS(SVG, 'svg');
    arrow.setAttribute('viewBox', '0 0 24 24');
    arrow.setAttribute('fill', 'currentColor');
    const shape = document.createElementNS(SVG, 'path');
    shape.setAttribute('d', POINTER_SHAPE);
    arrow.append(shape);
    parts.pointer.append(arrow);
    parts.dot = make('dot');
    parts.label = make('label');
    parts.detail = make('detail');
    parts.pill.append(parts.dot, parts.label, parts.detail);
    root.append(style, parts.edge, parts.target, parts.ring, parts.pointer, parts.pill);
    document.documentElement.append(host);
  }

  function clear() {
    if (!host) return;
    host.removeAttribute('data-tone');
    host.removeAttribute('data-working');
    parts.target.classList.remove('on');
    parts.pointer.classList.remove('on');
  }

  function colour(value, fallback) {
    // Only a plain colour is ever put into the page's styles.
    return typeof value === 'string' && /^#[0-9a-fA-F]{3,8}$/.test(value.trim()) ? value.trim() : fallback;
  }

  function box(value) {
    const numbers = value && [value.x, value.y, value.w, value.h];
    return numbers && numbers.every((number) => typeof number === 'number' && Number.isFinite(number)) ? value : null;
  }

  function show(look) {
    if (!TONES.includes(look.tone)) {
      clear();
      return;
    }
    if (!host) build();
    if (!host.isConnected) document.documentElement.append(host);
    host.style.setProperty('--tone', colour(look.colour, '#6E3B83'));
    host.style.setProperty('--on-tone', colour(look.onColour, '#FFFFFF'));
    host.setAttribute('data-tone', look.tone);
    host.toggleAttribute('data-working', look.working === true);
    parts.label.textContent = typeof look.label === 'string' ? look.label : '';
    parts.detail.textContent = typeof look.detail === 'string' ? look.detail : '';
    parts.detail.hidden = !parts.detail.textContent;

    const target = box(look.target);
    parts.target.classList.toggle('on', Boolean(target));
    if (target) {
      Object.assign(parts.target.style, { left: `${target.x}px`, top: `${target.y}px`, width: `${target.w}px`, height: `${target.h}px` });
    }
    const at = box(look.pointer && { ...look.pointer, w: 0, h: 0 });
    parts.pointer.classList.toggle('on', Boolean(at));
    if (at) {
      parts.pointer.style.transform = `translate(${at.x}px, ${at.y}px)`;
      if (typeof look.click === 'number' && look.click !== lastClick) {
        // One ring for each click, where the pointer is.
        lastClick = look.click;
        Object.assign(parts.ring.style, { left: `${at.x}px`, top: `${at.y}px` });
        parts.ring.classList.remove('go');
        void parts.ring.offsetWidth;
        parts.ring.classList.add('go');
      }
    }
  }

  chrome.runtime.onMessage.addListener((message) => {
    if (typeof message !== 'object' || message === null || message.type !== LOOK) return;
    clearTimeout(forget);
    forget = setTimeout(clear, FORGET_MS);
    show(message);
  });
})();
