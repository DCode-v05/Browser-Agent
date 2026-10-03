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

  function kids(el, a) {
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
      ref = 'e' + state.next++;
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
      emit('Page: ' + clean(document.title, a.maxText));
      emit('URL: ' + clean(location.href, a.maxText));
      emit(`Scroll: ${Math.round(scrollY)}px of ${document.documentElement.scrollHeight}px (viewport ${innerHeight}px)`);
      visit(root, 0, 0, false, true);
    } catch (error) {
      if (error !== STOP) throw error;
    }
    if (truncated) lines.push(a.notice);
    return { text: lines.join('\n'), next: state.next, truncated };
  }

  // Resolves at the next animation frame, or after `ms` on a page that is not being painted.
  const nextFrame = (ms) =>
    new Promise((done) => {
      const timer = setTimeout(done, ms);
      requestAnimationFrame(() => {
        clearTimeout(timer);
        done();
      });
    });

  async function frames(a) {
    for (let i = 0; i < a.count; i++) await nextFrame(a.frameMs);
    return true;
  }

  const operations = { snapshot, frames };

  globalThis.__bap = (operation, a) => {
    const run = operations[operation];
    if (!run) throw new Error('unknown operation ' + operation);
    return run(a);
  };

  // Shared with the action operations added to this file.
  globalThis.__bapParts = { refs, resolve, roleOf, nameOf, textOf, visibility, nextFrame, quote, inputType, operations, SHOWN, TEXT_INPUT_TYPES };
})();

// Operations that prepare an element for an action. The driver then sends the real input events.
(() => {
  if (globalThis.__bap.withActions) return;
  const { resolve, roleOf, nameOf, textOf, visibility, nextFrame, quote, inputType, operations, SHOWN, TEXT_INPUT_TYPES } =
    globalThis.__bapParts;

  function describe(el, a) {
    const role = roleOf(el) || el.tagName.toLowerCase();
    const name = nameOf(el, role, a) || textOf(el, a.maxName, a);
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
    let lastBox = '';
    for (;;) {
      if (!el.isConnected) return { error: 'stale' };
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
          reason = 'it is still moving';
        } else {
          const hit = elementAt(point.x, point.y);
          if (hit && (within(hit, el) || labelOf(hit, el))) return { x: point.x, y: point.y, describe: described };
          reason = hit ? 'it is covered by ' + describe(hit, a) : 'it is outside the visible area';
        }
      }
      if (performance.now() >= deadline) return { error: 'not_ready', reason, describe: described };
      await nextFrame(a.frameMs);
    }
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

  operations.prepare = prepare;
  operations.focus = focus;
  globalThis.__bap.withActions = true;
})();
