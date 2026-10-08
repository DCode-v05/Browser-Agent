// Reads a document and prepares its elements for actions. It runs in an isolated world, so the
// page's own scripts cannot see it or change it. One entry point: __bap(operation, arguments).
(() => {
  if (globalThis.__bap) return;

  const refs = new Map(); // ref -> WeakRef(element): never keeps a removed element alive
  const ids = new WeakMap(); // element -> ref: an element keeps its ref while its document lives

  const GONE = 0; // not rendered, and nothing below it is
  const SELF_HIDDEN = 1; // not shown itself; its children may be
  const SHOWN = 2;

  const SKIPPED_TAGS = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'HEAD', 'META', 'LINK', 'TITLE']);
  const INLINE_TAGS = new Set(['SPAN', 'B', 'I', 'EM', 'STRONG', 'A', 'CODE', 'SMALL', 'SUB', 'SUP', 'U', 'MARK', 'ABBR', 'FONT']);
  const INPUT_ROLES = {
    text: 'textbox', email: 'textbox', tel: 'textbox', url: 'textbox', password: 'textbox',
    search: 'searchbox', number: 'spinbutton', checkbox: 'checkbox', radio: 'radio', range: 'slider',
    button: 'button', submit: 'button', reset: 'button', image: 'button', file: 'button',
  };
  const TAG_ROLES = {
    BUTTON: 'button', TEXTAREA: 'textbox', SUMMARY: 'button', IFRAME: 'iframe', DIALOG: 'dialog',
    H1: 'heading', H2: 'heading', H3: 'heading', H4: 'heading', H5: 'heading', H6: 'heading',
    OPTION: 'option', NAV: 'navigation', MAIN: 'main', UL: 'list', OL: 'list', LI: 'listitem',
    TABLE: 'table', TR: 'row', TD: 'cell', TH: 'columnheader', FORM: 'form', P: 'paragraph',
    HEADER: 'banner', FOOTER: 'contentinfo', ASIDE: 'complementary',
  };
  const INTERACTIVE = new Set([
    'button', 'link', 'textbox', 'searchbox', 'spinbutton', 'combobox', 'listbox', 'checkbox', 'radio',
    'switch', 'slider', 'tab', 'menuitem', 'menuitemcheckbox', 'menuitemradio', 'option', 'treeitem',
    'iframe', 'clickable',
  ]);
  const ALSO_LISTED = new Set(['heading', 'dialog', 'alertdialog', 'alert']);
  const NAMED_BY_CONTENT = new Set([
    'button', 'link', 'heading', 'option', 'tab', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
    'treeitem', 'clickable', 'checkbox', 'radio', 'switch',
  ]);
  const CHECKABLE = new Set(['checkbox', 'radio', 'switch', 'menuitemcheckbox', 'menuitemradio']);
  const VALUE_ROLES = new Set(['textbox', 'searchbox', 'spinbutton', 'slider']);
  const TEXT_INPUT_TYPES = new Set(['text', 'email', 'tel', 'url', 'password', 'search', 'number']);
  const PLAIN_WORD = /^[a-z-]+$/; // a role or type from the page is used only when it is a plain word
  const STOP = Symbol('stop');

  const quote = (text) => JSON.stringify(text);

  function clean(text, limit) {
    const flat = (text || '').replace(/\s+/g, ' ').trim();
    if (flat.length <= limit) return flat;
    return Array.from(flat).slice(0, limit - 1).join('') + '\u2026';
  }

  function inputType(el) {
    const type = (el.getAttribute('type') || 'text').toLowerCase();
    return PLAIN_WORD.test(type) ? type : 'text';
  }

  function visibility(el) {
    if (SKIPPED_TAGS.has(el.tagName) || el.getAttribute('aria-hidden') === 'true' || el.inert) return GONE;
    if (el.checkVisibility({ visibilityProperty: true })) return SHOWN;
    if (el.checkVisibility()) return SELF_HIDDEN; // visibility:hidden hides the element, not its children
    // An element with no box of its own still renders its children.
    return getComputedStyle(el).display === 'contents' ? SELF_HIDDEN : GONE;
  }

  function roleOf(el) {
    const explicit = (el.getAttribute('role') || '').trim().split(/\s+/)[0].toLowerCase();
    if (explicit === 'presentation' || explicit === 'none') return '';
    if (explicit && PLAIN_WORD.test(explicit)) return explicit;
    const tag = el.tagName;
    if (tag === 'INPUT') {
      const type = inputType(el);
      return type === 'hidden' ? '' : INPUT_ROLES[type] || 'textbox';
    }
    if (tag === 'A') return el.hasAttribute('href') ? 'link' : '';
    if (tag === 'SELECT') return el.multiple || el.size > 1 ? 'listbox' : 'combobox';
    if (tag === 'IMG') return el.getAttribute('alt') === '' ? '' : 'img';
    if (tag === 'SECTION') {
      return el.hasAttribute('aria-label') || el.hasAttribute('aria-labelledby') ? 'region' : '';
    }
    const editable = el.getAttribute('contenteditable');
    if (editable !== null && editable !== 'false') return 'textbox';
    return TAG_ROLES[tag] || '';
  }

  // Things that only behave like buttons: a click handler attribute, a tab index, or a pointer
  // cursor that is not inherited from the parent. The style lookup runs only for elements that
  // reach this far: no role, no handler attribute, no tab index.
  function looksClickable(el) {
    if (el.hasAttribute('onclick')) return true;
    const tabIndex = el.getAttribute('tabindex');
    if (tabIndex !== null && Number(tabIndex) >= 0) return true;
    if (getComputedStyle(el).cursor !== 'pointer') return false;
    const parent = el.parentElement;
    return !parent || getComputedStyle(parent).cursor !== 'pointer';
  }

  // How often the document has changed since this script was put in it (spec 18.8): its
  // structure, what was typed or chosen, what was scrolled, and where the keyboard put the focus.
  // A focus that a press of the pointer brought is not counted: a dead button pressed twice
  // changes nothing the second time.
  let changes = 0;
  let pointerIsDown = false;
  const WATCHED = { subtree: true, childList: true, attributes: true, characterData: true };
  const watcher = new MutationObserver(() => changes++);
  const watchedRoots = new WeakSet();
  // A shadow root is a tree of its own: the watcher of the document does not see into it.
  function watch(root) {
    if (watchedRoots.has(root)) return;
    watchedRoots.add(root);
    watcher.observe(root, WATCHED);
  }
  watch(document);
  const seen = { capture: true, passive: true };
  for (const type of ['input', 'change', 'scroll']) addEventListener(type, () => changes++, seen);
  addEventListener('pointerdown', () => (pointerIsDown = true), seen);
  for (const type of ['pointerup', 'pointercancel', 'keydown']) addEventListener(type, () => (pointerIsDown = false), seen);
  addEventListener('focusin', () => pointerIsDown || changes++, seen);

  function stamp() {
    // What the watcher has seen and not yet told.
    if (watcher.takeRecords().length) changes++;
    return changes;
  }

  function kids(el, a) {
    if (el.shadowRoot) watch(el.shadowRoot);
    if (a.shadow && el.shadowRoot) return el.shadowRoot.childNodes;
    if (el.tagName === 'SLOT') {
      const assigned = el.assignedNodes({ flatten: true });
      return assigned.length ? assigned : el.childNodes;
    }
    return el.childNodes;
  }

  // The rendered text inside an element, without the text of form controls.
  function textOf(el, limit, a) {
    let out = '';
    const walk = (node) => {
      if (out.length > limit * 2) return;
      const shown = visibility(node);
      if (shown === GONE) return;
      const tag = node.tagName;
      if (tag === 'SELECT' || tag === 'TEXTAREA') return;
      if (tag === 'IMG') {
        out += ' ' + (node.getAttribute('alt') || '') + ' ';
        return;
      }
      for (const child of kids(node, a)) {
        if (child.nodeType === 3) {
          if (shown === SHOWN) out += child.nodeValue;
        } else if (child.nodeType === 1) walk(child);
      }
      if (!INLINE_TAGS.has(tag)) out += ' ';
    };
    walk(el);
    return clean(out, limit);
  }

  function nameOf(el, role, a) {
    const limit = a.maxName;
    const labelledBy = el.getAttribute('aria-labelledby');
    if (labelledBy) {
      const root = el.getRootNode();
      const text = labelledBy
        .split(/\s+/)
        .map((id) => {
          const target = root.getElementById ? root.getElementById(id) : null;
          return target ? textOf(target, limit, a) : '';
        })
        .join(' ');
      if (text.trim()) return clean(text, limit);
    }
    const label = el.getAttribute('aria-label');
    if (label && label.trim()) return clean(label, limit);
    const tag = el.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
      const fromLabels = Array.from(el.labels || [], (item) => textOf(item, limit, a)).join(' ');
      if (fromLabels.trim()) return clean(fromLabels, limit);
      if (tag === 'INPUT') {
        const type = inputType(el);
        if (type === 'submit') return clean(el.value || 'Submit', limit);
        if (type === 'reset') return clean(el.value || 'Reset', limit);
        if (type === 'button') return clean(el.value, limit);
        if (type === 'image') return clean(el.getAttribute('alt') || el.getAttribute('title') || 'Submit', limit);
      }
      return clean(el.getAttribute('title') || el.getAttribute('placeholder') || '', limit);
    }
    if (tag === 'IMG') return clean(el.getAttribute('alt') || el.getAttribute('title') || '', limit);
    if (tag === 'IFRAME') return clean(el.getAttribute('title') || el.getAttribute('name') || '', limit);
    if (NAMED_BY_CONTENT.has(role)) {
      const text = textOf(el, limit, a);
      if (text) return text;
    }
    return clean(el.getAttribute('title') || '', limit);
  }

  function statesOf(el, role) {
    const out = [];
    const aria = (name) => el.getAttribute('aria-' + name);
    if (role === 'heading') {
      const level = aria('level');
      out.push(`[level=${/^[1-9]$/.test(level || '') ? level : /^H[1-6]$/.test(el.tagName) ? el.tagName[1] : '2'}]`);
    }
    if (CHECKABLE.has(role)) {
      const value = el.tagName === 'INPUT' ? (el.indeterminate ? 'mixed' : String(el.checked)) : aria('checked');
      out.push(value === 'true' ? '[checked]' : value === 'mixed' ? '[mixed]' : '[unchecked]');
    }
    if (el.required === true || aria('required') === 'true') out.push('[required]');
    if (el.matches(':disabled') || aria('disabled') === 'true') out.push('[disabled]');
    if (el.readOnly === true || aria('readonly') === 'true') out.push('[readonly]');
    const details = el.tagName === 'SUMMARY' && el.parentElement && el.parentElement.tagName === 'DETAILS';
    const expanded = details ? String(el.parentElement.open) : aria('expanded');
    if (expanded === 'true') out.push('[expanded]');
    else if (expanded === 'false') out.push('[collapsed]');
    if (aria('selected') === 'true') out.push('[selected]');
    if (aria('pressed') === 'true') out.push('[pressed]');
    return out;
  }

  function valuesOf(el, role, name, a) {
    const out = [];
    const tag = el.tagName;
    if (tag === 'SELECT') {
      const labels = Array.from(el.options, (option) => clean(option.label, a.maxValue));
      const chosen = Array.from(el.selectedOptions, (option) => clean(option.label, a.maxValue));
      out.push('value=' + quote(el.multiple ? chosen.join(', ') : chosen[0] || ''));
      const shown = labels.slice(0, a.maxOptions);
      if (labels.length > shown.length) shown.push(`\u2026 ${labels.length - shown.length} more`);
      out.push('options=' + JSON.stringify(shown));
      return out;
    }
    if (tag === 'INPUT' || tag === 'TEXTAREA') {
      const type = tag === 'INPUT' ? inputType(el) : 'text';
      if (VALUE_ROLES.has(role)) {
        if (el.value) {
          // A password is shown as a fixed row of dots: neither its text nor its length leaves the page.
          out.push('value=' + quote(type === 'password' ? '\u2022'.repeat(8) : clean(el.value, a.maxValue)));
        } else {
          const hint = clean(el.getAttribute('placeholder') || '', a.maxValue);
          if (hint && hint !== name) out.push('placeholder=' + quote(hint));
        }
      }
      if (tag === 'INPUT' && type !== 'text' && (VALUE_ROLES.has(role) || type === 'file')) out.push('type=' + type);
      return out;
    }
    if (role === 'textbox') {
      const text = textOf(el, a.maxValue, a);
      if (text) out.push('value=' + quote(text));
    }
    return out;
  }

  function lineFor(el, role, indent, a, state) {
    let ref = ids.get(el);
    if (!ref) {
      // A ref inside a frame begins with the frame's name: f2e7.
      ref = (a.prefix || '') + 'e' + state.next++;
      ids.set(el, ref);
      refs.set(ref, new WeakRef(el));
    }
    const name = nameOf(el, role, a);
    const parts = ['  '.repeat(indent) + '- ' + role];
    if (name) parts.push(quote(name));
    parts.push(`[ref=${ref}]`, ...statesOf(el, role), ...valuesOf(el, role, name, a));
    if (a.bboxes) {
      const box = el.getBoundingClientRect();
      parts.push(`[box=${[box.x, box.y, box.width, box.height].map(Math.round).join(',')}]`);
    }
    return parts.join(' ');
  }

  function resolve(ref) {
    const weak = refs.get(ref);
    const el = weak && weak.deref();
    return el && el.isConnected ? el : null;
  }

  function snapshot(a) {
    const state = { next: a.next };
    const lines = [];
    // The frames met on the way: the driver reads each one and puts it under its line.
    const framesMet = [];
    let size = 0;
    let truncated = false;
    const budget = a.maxChars - a.notice.length - 1;
    // The walk stops here when the cap is reached. It does not read the rest of the page.
    const emit = (line) => {
      if (size + line.length + 1 > budget) {
        truncated = true;
        throw STOP;
      }
      lines.push(line);
      size += line.length + 1;
    };

    const visit = (node, depth, indent, named, parentShown) => {
      if (node.nodeType === 3) {
        if (a.mode === 'all' && !named && parentShown) {
          const text = clean(node.nodeValue, a.maxText);
          if (text) emit('  '.repeat(indent) + '- text ' + quote(text));
        }
        return;
      }
      if (node.nodeType !== 1) return;
      const seen = visibility(node);
      if (seen === GONE) return;
      const shown = seen === SHOWN;
      let role = shown ? roleOf(node) : '';
      let listed = INTERACTIVE.has(role) || ALSO_LISTED.has(role);
      if (shown && !listed && !named && looksClickable(node)) {
        role = 'clickable';
        listed = true;
      }
      let childIndent = indent;
      let childNamed = named;
      if (role && (listed || a.mode === 'all')) {
        emit(lineFor(node, role, indent, a, state));
        if (node.tagName === 'IFRAME') framesMet.push({ ref: ids.get(node), line: lines.length - 1, indent });
        childIndent = indent + 1;
        childNamed = named || NAMED_BY_CONTENT.has(role);
      }
      const tag = node.tagName;
      // A select's options and a text area's text are in its own line; a frame is read separately.
      if (tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'IFRAME' || depth >= a.maxDepth) return;
      for (const child of kids(node, a)) visit(child, depth + 1, childIndent, childNamed, shown);
    };

    let root = document.body || document.documentElement;
    if (a.ref) {
      root = resolve(a.ref);
      if (!root) return { error: 'stale' };
    }
    try {
      // A frame read as part of its page has no heading of its own.
      if (!a.embedded) {
        emit('Page: ' + clean(document.title, a.maxText));
        emit('URL: ' + clean(location.href, a.maxText));
        emit(`Scroll: ${Math.round(scrollY)}px of ${document.documentElement.scrollHeight}px (viewport ${innerHeight}px)`);
      }
      visit(root, 0, a.indent || 0, false, true);
    } catch (error) {
      if (error !== STOP) throw error;
    }
    if (truncated) lines.push(a.notice);
    return { text: lines.join('\n'), next: state.next, truncated, frames: framesMet };
  }

  // Resolves at the next animation frame, or after `ms` on a page that is not being painted.
  // Waits for the browser's next frame, and no longer than `ms`: a page that is not being drawn
  // has no frames. Says whether a frame was drawn.
  const nextFrame = (ms) =>
    new Promise((done) => {
      const timer = setTimeout(() => done(false), ms);
      requestAnimationFrame(() => {
        clearTimeout(timer);
        done(true);
      });
    });

  async function frames(a) {
    for (let i = 0; i < a.count; i++) await nextFrame(a.frameMs);
    return true;
  }

  // Lets the page do what an action has just set going: a form it sends, a script that leaves.
  // Two turns of the page's own queue, with no wait for anything to be drawn.
  async function turn() {
    for (let i = 0; i < 2; i++) await new Promise((done) => setTimeout(done, 0));
    return true;
  }

  const operations = { snapshot, frames, turn, stamp };

  globalThis.__bap = (operation, a) => {
    const run = operations[operation];
    if (!run) throw new Error('unknown operation ' + operation);
    return run(a);
  };

  // Shared with the action operations added to this file.
  globalThis.__bapParts = { INTERACTIVE, refs, resolve, roleOf, nameOf, textOf, visibility, nextFrame, quote, inputType, operations, clean, snapshot, SHOWN, TEXT_INPUT_TYPES, VALUE_ROLES, CHECKABLE };
})();

// Operations that prepare an element for an action. The driver then sends the real input events.
(() => {
  if (globalThis.__bap.withActions) return;
  const { INTERACTIVE, refs, resolve, roleOf, nameOf, textOf, visibility, nextFrame, quote, inputType, operations, clean, snapshot, SHOWN, TEXT_INPUT_TYPES, VALUE_ROLES, CHECKABLE } =
    globalThis.__bapParts;

  // What an element is and what it is called. What a field holds is what was typed into it, so a
  // field with no label has no name: its content never stands in for one.
  function identify(el, a) {
    const role = roleOf(el) || el.tagName.toLowerCase();
    const holdsTypedText = VALUE_ROLES.has(role) || role === 'combobox' || el.isContentEditable;
    return { role, name: nameOf(el, role, a) || (holdsTypedText ? '' : textOf(el, a.maxName, a)) };
  }

  function describe(el, a) {
    const { role, name } = identify(el, a);
    return name ? `${role} ${quote(name)}` : role;
  }

  // True when `node` is `ancestor` or sits inside it, looking through shadow roots.
  function within(node, ancestor) {
    for (let current = node; current; current = current.parentNode || current.host) {
      if (current === ancestor) return true;
    }
    return false;
  }

  function labelOf(hit, el) {
    return Array.from(el.labels || []).some((label) => within(hit, label));
  }

  function elementAt(x, y) {
    let root = document;
    let hit = null;
    for (;;) {
      const found = root.elementFromPoint(x, y);
      if (!found || found === hit) return hit;
      hit = found;
      if (!found.shadowRoot) return hit;
      root = found.shadowRoot;
    }
  }

  function target(el) {
    for (const rect of el.getClientRects()) {
      if (rect.width > 0 && rect.height > 0) {
        return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, box: [rect.left, rect.top, rect.width, rect.height].join() };
      }
    }
    return null;
  }

  const disabled = (el) => el.matches(':disabled') || el.getAttribute('aria-disabled') === 'true';

  // Waits until the element is visible, enabled, holding still and not covered, then gives the
  // point to click. When the time runs out it says which of these failed.
  async function prepare(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const described = describe(el, a);
    const deadline = performance.now() + a.timeoutMs;
    // Whether the browser drew a frame during the last wait.
    let drawn = true;
    let lastBox = '';
    // The frame the element was last looked at in. The page's own clock moves on with each frame
    // the browser draws, and stands still between them.
    let lastFrame = null;
    let broughtIntoView = false;
    for (;;) {
      if (!el.isConnected) return { error: 'stale' };
      const frame = document.timeline.currentTime;
      let reason;
      if (visibility(el) !== SHOWN) reason = 'it is not visible';
      else if (disabled(el)) reason = 'it is disabled';
      else {
        let point = target(el);
        if (point && (point.x < 0 || point.y < 0 || point.x >= innerWidth || point.y >= innerHeight)) {
          el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
          point = target(el);
        }
        if (!point) reason = 'it has no size';
        else if (point.box !== lastBox) {
          lastBox = point.box;
          lastFrame = frame;
          reason = 'it is still moving';
        } else if (drawn && frame !== null && frame === lastFrame) {
          // The element is where it was, but this is still the frame it was last looked at in: the
          // wait ended inside a frame that was already under way. The page has not moved on, so
          // looking twice told nothing. The next frame tells.
          reason = 'it is still moving';
        } else {
          const hit = elementAt(point.x, point.y);
          if (hit && (within(hit, el) || labelOf(hit, el))) return { x: point.x, y: point.y, describe: described };
          if (!broughtIntoView) {
            // Inside a list or a dialog that scrolls by itself, the element can be within the window
            // and still out of sight. It is brought into view once before it is called covered.
            broughtIntoView = true;
            el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
            lastBox = '';
          }
          reason = hit ? 'it is covered by ' + describe(hit, a) : 'it is outside the visible area';
        }
      }
      if (performance.now() >= deadline) return { error: 'not_ready', reason, describe: described };
      // On a page that is not being drawn no frame comes, its clock stands still, and nothing in
      // it moves: there the wait ends by its time, and the same place twice is holding still.
      drawn = await nextFrame(a.frameMs);
    }
  }

  // After the pointer has gone to the point it will press, the page may have moved: a menu that
  // was open under the pointer closes, and what follows it shifts. True when the element is still there.
  async function holds(a) {
    await nextFrame(a.frameMs);
    const el = resolve(a.ref);
    if (!el) return false;
    const hit = elementAt(a.x, a.y);
    return Boolean(hit) && (within(hit, el) || labelOf(hit, el));
  }

  function focused() {
    let el = document.activeElement;
    while (el && el.shadowRoot && el.shadowRoot.activeElement) el = el.shadowRoot.activeElement;
    return el;
  }

  // Focuses a text field and selects what it holds (or puts the caret at its end), so that the
  // text the driver inserts next replaces it (or follows it).
  function focus(a) {
    const el = a.ref ? resolve(a.ref) : focused();
    if (a.ref && !el) return { error: 'stale' };
    if (!el || el === document.body || el === document.documentElement) return { error: 'nothing_focused' };
    const described = describe(el, a);
    const tag = el.tagName;
    const field = tag === 'TEXTAREA' || (tag === 'INPUT' && TEXT_INPUT_TYPES.has(inputType(el)));
    if (!field && !el.isContentEditable) return { error: 'not_editable', describe: described };
    if (visibility(el) !== SHOWN) return { error: 'not_ready', reason: 'it is not visible', describe: described };
    if (disabled(el) || el.readOnly === true) {
      return { error: 'not_ready', reason: 'it is disabled or read-only', describe: described };
    }
    el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
    el.focus();
    // A page can send the focus elsewhere as soon as it arrives. What is typed next would land there.
    const active = focused();
    if (active !== el && !(el.isContentEditable && active && active.contains(el))) {
      return { error: 'not_ready', reason: 'the page moved the focus to another element', describe: described };
    }
    let hadText;
    if (field) {
      hadText = el.value.length > 0;
      if (a.clear) el.select();
      else {
        try {
          el.setSelectionRange(el.value.length, el.value.length);
        } catch {
          // Email and number fields have no selection range; after focus the caret is already at the end.
        }
      }
    } else {
      hadText = el.textContent.length > 0;
      const range = document.createRange();
      range.selectNodeContents(el);
      if (!a.clear) range.collapse(false);
      const selection = getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
    return { describe: described, hadText };
  }

  const isTextField = (el) =>
    el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && TEXT_INPUT_TYPES.has(inputType(el))) || el.isContentEditable;

  // The control that a press at a point lands on: the element there, or the control it is part of.
  function pressedAt(x, y) {
    const hit = elementAt(x, y);
    for (let el = hit; el && el !== document.documentElement; el = el.parentElement || el.getRootNode().host) {
      if (INTERACTIVE.has(roleOf(el))) return el;
    }
    return hit;
  }

  const textFieldsOf = (form) => Array.from(form.querySelectorAll('input, textarea, [contenteditable]')).filter(isTextField);

  // A box people search in: a search field, or the one field of its form.
  function isSearchBox(el) {
    if (el.tagName !== 'INPUT') return roleOf(el) === 'searchbox';
    const form = el.form;
    return inputType(el) === 'search' || roleOf(el) === 'searchbox' || (Boolean(form) && textFieldsOf(form).length === 1);
  }

  // Whether pressing an element sends the form it is in.
  function sendsItsForm(el) {
    const type = (el.getAttribute('type') || '').toLowerCase();
    if (el.tagName === 'BUTTON') return type !== 'button' && type !== 'reset';
    return el.tagName === 'INPUT' && (type === 'submit' || type === 'image');
  }

  // The nearest part of the page around a control that says more than the control itself.
  const LEVELS_AROUND = 4;
  function blockAround(el) {
    const own = (el.innerText || '').length;
    let around = el;
    for (let up = 0; up < LEVELS_AROUND && around.parentElement && around.parentElement !== document.body; up++) {
      around = around.parentElement;
      if ((around.innerText || '').length > own) break;
    }
    return around;
  }

  // What the check needs to know of an element besides its name (spec 18.4, 18.6): of a field,
  // what kind of thing is typed into it; of a control that is pressed, what pressing it sends
  // and what stands near it.
  const FIELDS_OF_A_FORM = 20;
  function facts(el, a) {
    const tag = el.tagName;
    const out = { document: tag === 'IFRAME' && el.src ? el.src : location.href };
    if (isTextField(el)) {
      const type = tag === 'INPUT' ? inputType(el) : '';
      out.inputType = type;
      out.autocomplete = (el.getAttribute('autocomplete') || '').trim().toLowerCase();
      out.attributes = [el.getAttribute('name'), el.id].filter(Boolean).map((text) => clean(text, a.maxName));
      out.dots = type !== 'password' && (getComputedStyle(el).webkitTextSecurity || 'none') !== 'none';
      out.multiline = tag !== 'INPUT';
      out.search = isSearchBox(el);
    } else if (a.press) {
      const form = el.form || el.closest('form');
      if (form && sendsItsForm(el)) {
        out.sendsForm = textFieldsOf(form)
          .slice(0, FIELDS_OF_A_FORM)
          .map((field) => [roleOf(field) || 'textbox', nameOf(field, roleOf(field), a) || '', field.tagName !== 'INPUT', isSearchBox(field)]);
      }
      out.around = [form ? clean(form.innerText || '', a.maxAround) : '', clean(blockAround(el).innerText || '', a.maxAround)];
    }
    return out;
  }

  // What an element is and where, without touching the page. Without a ref: the control at a
  // point, or the element that has the focus.
  function locate(a) {
    const el = a.ref ? resolve(a.ref) : a.focused ? focused() : pressedAt(a.x, a.y);
    if (a.ref && !el) return { error: 'stale' };
    if (!el || el === document.body || el === document.documentElement) return { error: 'nothing' };
    const point = target(el);
    const shown = point && point.x >= 0 && point.y >= 0 && point.x < innerWidth && point.y < innerHeight;
    const secret = el.tagName === 'INPUT' && inputType(el) === 'password';
    return {
      ...identify(el, a),
      secret,
      kind: kindOf(el),
      box: shown ? point.box.split(',').map(Number) : null,
      ...facts(el, a),
    };
  }

  // What the page says it is about, in a few words: its headings and its buttons (spec 18.6).
  function gist(a) {
    const said = [];
    for (const el of document.querySelectorAll('h1, h2, h3, [role=heading], button, [role=button], input[type=submit]')) {
      if (said.length >= a.limit) break;
      if (visibility(el) !== SHOWN) continue;
      const text = clean(el.innerText || el.value || el.getAttribute('aria-label') || '', a.maxName);
      if (text) said.push(text);
    }
    return said;
  }

  const isNativeCheck = (el) => el.tagName === 'INPUT' && (inputType(el) === 'checkbox' || inputType(el) === 'radio');

  // How a form field is filled: by typing, by ticking, or by choosing an option.
  function kindOf(el) {
    if (el.tagName === 'SELECT') return 'select';
    if (isNativeCheck(el) || CHECKABLE.has(roleOf(el))) return 'check';
    return isTextField(el) ? 'text' : 'other';
  }

  // The rendered text of the page or of one element. What a field holds is not part of it.
  function text(a) {
    const el = a.ref ? resolve(a.ref) : document.body;
    if (a.ref && !el) return { error: 'stale' };
    if (!el) return { text: '', more: 0 };
    const all = (el.innerText ?? el.textContent ?? '')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
    const shown = Array.from(all).slice(0, a.maxChars).join('');
    return { text: shown, more: all.length - shown.length };
  }

  // The nearest thing around an element that scrolls by itself: a list, a panel, a dialog.
  function scroller(el) {
    for (let node = el; node && node !== document.body && node !== document.documentElement; node = node.parentElement || (node.getRootNode() || {}).host) {
      const style = getComputedStyle(node);
      const scrolls = (value) => value === 'auto' || value === 'scroll';
      if ((scrolls(style.overflowY) && node.scrollHeight > node.clientHeight) || (scrolls(style.overflowX) && node.scrollWidth > node.clientWidth)) return node;
    }
    return null;
  }

  // Where the page, or the box an element scrolls in, is scrolled to. It waits until the position
  // has held still for two checks, or the time has run out.
  async function scrolled(a) {
    const el = a.ref ? resolve(a.ref) : null;
    if (a.ref && !el) return { error: 'stale' };
    const box = el && scroller(el);
    const doc = document.documentElement;
    const read = () => (box ? [box.scrollLeft, box.scrollTop] : [scrollX, scrollY]);
    const deadline = performance.now() + a.timeoutMs;
    let last = '';
    for (;;) {
      const now = read().join();
      if (now === last || performance.now() >= deadline) break;
      last = now;
      await nextFrame(a.frameMs);
    }
    const [x, y] = read().map(Math.round);
    return box
      ? { x, y, width: box.scrollWidth, height: box.scrollHeight, inside: true }
      : { x, y, width: doc.scrollWidth, height: doc.scrollHeight, inside: false };
  }

  // Where the wheel is turned to scroll at an element: the middle of the box it scrolls in, or
  // its own middle when it is in no such box. It is brought into view first when it is outside
  // what the browser shows.
  function wheelPoint(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const described = describe(el, a);
    const box = scroller(el) || el;
    const outside = (at) => at.x < 0 || at.y < 0 || at.x >= innerWidth || at.y >= innerHeight;
    let at = target(box);
    if (at && outside(at)) {
      box.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
      at = target(box);
    }
    if (!at || outside(at)) return { error: 'not_ready', reason: 'it is not visible', describe: described };
    return { x: at.x, y: at.y, describe: described };
  }

  // What is at a point of the page, as the snapshot names it.
  function at(a) {
    const hit = elementAt(a.x, a.y);
    return { describe: hit ? describe(hit, a) : '' };
  }

  function reveal(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
    return { describe: describe(el, a) };
  }

  // Gives an element the keyboard focus, whatever it is, so that a key press goes to it.
  function focusOn(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const described = describe(el, a);
    if (visibility(el) !== SHOWN) return { error: 'not_ready', reason: 'it is not visible', describe: described };
    el.focus();
    return { describe: described };
  }

  const optionLabel = (option) => (option.label || option.text || '').replace(/\s+/g, ' ').trim();

  // Chooses options in a dropdown or a list, by value or by label, and tells the page as a person's
  // choice would: an input event, then a change event.
  function select(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const described = describe(el, a);
    if (el.tagName !== 'SELECT') return { error: 'not_select', describe: described };
    if (visibility(el) !== SHOWN) return { error: 'not_ready', reason: 'it is not visible', describe: described };
    if (disabled(el)) return { error: 'not_ready', reason: 'it is disabled', describe: described };
    if (a.values.length > 1 && !el.multiple) return { error: 'one_only', describe: described };
    const options = Array.from(el.options);
    const chosen = [];
    for (const want of a.values) {
      const low = want.trim().toLowerCase();
      const option =
        options.find((o) => o.value === want || optionLabel(o) === want.trim()) ||
        options.find((o) => o.value.toLowerCase() === low || optionLabel(o).toLowerCase() === low);
      if (!option) {
        return { error: 'no_option', want: clean(want, a.maxName), options: options.slice(0, a.maxOptions).map(optionLabel), describe: described };
      }
      if (option.disabled) return { error: 'not_ready', reason: 'the option ' + quote(optionLabel(option)) + ' is disabled', describe: described };
      chosen.push(option);
    }
    el.focus();
    for (const option of options) option.selected = chosen.includes(option);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return { describe: described, selected: chosen.map(optionLabel) };
  }

  // Whether a checkbox, a radio button or a switch is on.
  function checkable(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const described = describe(el, a);
    const role = roleOf(el);
    if (!isNativeCheck(el) && !CHECKABLE.has(role)) return { error: 'not_checkable', describe: described };
    const checked = isNativeCheck(el) ? el.checked : el.getAttribute('aria-checked') === 'true';
    return { describe: described, checked, radio: role === 'radio' || role === 'menuitemradio' };
  }

  // Waits until the rendered text of the page holds some words, or no longer holds them.
  async function waitText(a) {
    const want = a.text.replace(/\s+/g, ' ').trim().toLowerCase();
    const deadline = performance.now() + a.timeoutMs;
    for (;;) {
      const page = ((document.body && document.body.innerText) || '').replace(/\s+/g, ' ').toLowerCase();
      if (page.includes(want) !== a.gone) return { reached: true };
      if (performance.now() >= deadline) return { reached: false };
      await new Promise((done) => setTimeout(done, a.pollMs));
    }
  }

  // What the browser shows of the page and how large the whole page is, in page pixels, and how
  // many pixels of the screen one page pixel takes.
  function area() {
    const doc = document.documentElement;
    const body = document.body;
    return {
      x: scrollX,
      y: scrollY,
      width: innerWidth,
      height: innerHeight,
      fullWidth: Math.max(doc.scrollWidth, body ? body.scrollWidth : 0, innerWidth),
      fullHeight: Math.max(doc.scrollHeight, body ? body.scrollHeight : 0, innerHeight),
      ratio: devicePixelRatio,
    };
  }

  // The labels of an annotated screenshot: the ref of each control a snapshot has listed, drawn at
  // its corner. They are in the page only while the picture is taken, inside a closed shadow root,
  // and take no room in it.
  const LABEL_HEIGHT = 14;
  const LABEL_STYLE = `position:absolute;height:${LABEL_HEIGHT}px;padding:0 3px;border-radius:3px;font:bold 11px/${LABEL_HEIGHT}px sans-serif;white-space:nowrap;color:#fff;background:#b3261e`;
  const OUTLINE_STYLE = 'position:absolute;box-sizing:border-box;border:1px solid #b3261e';
  let labels = null;

  async function label(a) {
    if (labels) labels.remove();
    labels = null;
    if (!a.on) return { drawn: 0 };
    const host = document.createElement('div');
    host.style.cssText = 'position:absolute;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none';
    const root = host.attachShadow({ mode: 'closed' });
    let drawn = 0;
    for (const [ref, weak] of refs) {
      const el = weak.deref();
      if (!el || !el.isConnected || visibility(el) !== SHOWN) continue;
      const role = roleOf(el);
      // A heading or a paragraph has a ref too, and is not something to act on.
      if (role && !INTERACTIVE.has(role)) continue;
      const box = el.getBoundingClientRect();
      if (!box.width || !box.height) continue;
      const shown = box.right > 0 && box.bottom > 0 && box.left < innerWidth && box.top < innerHeight;
      if (!a.fullPage && !shown) continue;
      const left = box.left + scrollX;
      const top = box.top + scrollY;
      const outline = document.createElement('div');
      outline.style.cssText = `${OUTLINE_STYLE};left:${left}px;top:${top}px;width:${box.width}px;height:${box.height}px`;
      const tag = document.createElement('div');
      tag.textContent = ref;
      tag.style.cssText = `${LABEL_STYLE};left:${left}px;top:${Math.max(0, top - LABEL_HEIGHT)}px`;
      root.append(outline, tag);
      drawn++;
    }
    document.documentElement.append(host);
    labels = host;
    // The picture is taken of what has been painted.
    await nextFrame(a.frameMs);
    await nextFrame(a.frameMs);
    return { drawn };
  }

  // Where the page inside a frame begins, in this document's own window: the frame's box without
  // its border and padding. A point inside the frame is this far from the same point out here.
  function frameBox(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return {
      x: rect.left + el.clientLeft + parseFloat(style.paddingLeft || '0'),
      y: rect.top + el.clientTop + parseFloat(style.paddingTop || '0'),
    };
  }

  // Brings an element into view when its middle is outside what the window shows. One that can be
  // seen is left where it is, so the page does not jump at every action.
  function intoView(a) {
    const el = resolve(a.ref);
    if (!el) return { error: 'stale' };
    const middle = target(el);
    if (!middle || middle.x < 0 || middle.y < 0 || middle.x >= innerWidth || middle.y >= innerHeight) {
      el.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
    }
    return {};
  }

  // Makes a picture smaller, in the browser itself, so that no image library is needed. The picture
  // comes in and goes out as base64.
  async function shrink(a) {
    const bytes = Uint8Array.from(atob(a.data), (character) => character.charCodeAt(0));
    const bitmap = await createImageBitmap(new Blob([bytes], { type: a.mime }), {
      resizeWidth: a.width,
      resizeHeight: a.height,
      resizeQuality: 'high',
    });
    const canvas = new OffscreenCanvas(a.width, a.height);
    canvas.getContext('2d').drawImage(bitmap, 0, 0);
    bitmap.close();
    const blob = await canvas.convertToBlob({ type: a.mime, quality: a.quality });
    const smaller = new Uint8Array(await blob.arrayBuffer());
    let text = '';
    // In pieces: a call with every byte as an argument would be too long for the browser.
    for (let from = 0; from < smaller.length; from += a.piece) {
      text += String.fromCharCode.apply(null, smaller.subarray(from, from + a.piece));
    }
    return { data: btoa(text) };
  }

  Object.assign(operations, { locate, gist, prepare, holds, focus, text, scrolled, wheelPoint, at, reveal, focusOn, select, checkable, waitText, area, label, shrink, frameBox, intoView });
  globalThis.__bap.withActions = true;
})();
