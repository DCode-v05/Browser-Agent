# Milestone 1, Viewer Experience — Implementation Plan

**Goal:** The viewer a person watches and controls an agent through, built first and judged on its own: design tokens, every component and state, the settings screen, both themes, keyboard, screen reader, reduced motion, phone width. It runs on recorded sessions, so it needs no engine.

**Architecture:** One React page. One reducer turns the event stream into state; components render state and send commands. A `Connection` is the only thing that knows where events come from: a recorded session now (`?demo=`, `?state=`), the service's WebSocket in slice 4. The settings screen is drawn from the settings API's answer, served from a recorded file until slice 7.

**Tech Stack:** TypeScript, React, Vite, npm, Vitest with Testing Library, ESLint, axe-core. End-to-end checks of the built viewer run from `tests/viewer/` with pytest and Playwright.

**Spec:** `docs/bap-browser-spec.md` section 9 (all of it), 4.5 (states), 4.8 (protocol), 10.2 (settings), 12.5 (design-system and accessibility checklist), 14.1 slice 1.

## Global Constraints

- Only the tokens of spec 9.5 for colour, type, spacing, radius, shadow and motion. No colour, size or duration literal outside `viewer/src/tokens.css`.
- Every string a person reads comes from `viewer/src/wording.ts` and follows spec 9.6: sentence case, buttons start with a verb, a row under 60 characters.
- Every state has a label and an icon as well as a colour. Red means only blocked, failed or stop.
- Stop, pause and take over are always visible. Stop always asks for confirmation.
- Typed text never appears: a typing step shows a character count.
- WCAG 2.2 AA: keyboard reachable, visible focus ring, live regions, text contrast 4.5:1, controls 3:1, reflow at 200%, nothing by colour alone, no motion when reduced motion is asked for.
- Below 980 px the columns stack; the page never scrolls sideways; side gutter 16 px; smallest target 32 × 32 px.
- The viewer holds no list of settings: the settings screen is drawn from the settings answer.
- Nothing is injected into the visited page; the target highlight is drawn by the viewer.
- No dependency beyond React, Vite, Vitest, Testing Library, ESLint, axe-core and their required plugins and types.

## File Structure

```
viewer/
  package.json · vite.config.ts · tsconfig*.json · eslint.config.js · index.html
  scripts/record_demo.py        records the demo pictures with Playwright (run with uv)
  src/
    main.tsx · App.tsx
    tokens.css                  the design tokens (spec 9.5)
    styles/                     base, layout, components, settings
    wording.ts                  every string (spec 9.6, 9.7)
    protocol.ts                 events and commands (spec 4.8)
    state/
      reducer.ts                events -> state
      timeline.ts               steps -> rows: reads collapsed, idle dividers
      view.ts                   state -> what each state looks like (spec 9.3)
    connection/
      connection.ts             the Connection interface
      demo.ts                   plays a recorded session; answers commands
    demo/
      sessions.ts               the recorded sessions and the single states
      settings.ts               the settings answer for web, mobile and desktop
      frames/                   one picture per step
    components/                 one file per component of spec 9.4
    hooks/                      keyboard map, announcer, clock, theme
  tests live beside the code as *.test.ts(x)
tests/viewer/                   the built viewer: every state, both themes, keyboard, axe, phone width
```

## Tasks

Each task is test first for logic and components; pure styling is verified by running the viewer and looking.

- [ ] **Task 1: Scaffold.** `viewer/` with Vite, React, TypeScript, Vitest, ESLint; `npm run typecheck`, `lint`, `test`, `build` (build writes `src/bap_browser/viewer_dist/`); a viewer job in CI; commands in `CLAUDE.md`. Test: one component test passes. Verify: the four npm scripts run clean.
- [ ] **Task 2: Tokens and wording.** `tokens.css` with every token of 9.5 in light and dark; `wording.ts`. Tests: every colour pair of 9.5 meets its contrast ratio in both themes (computed in the test from the token file); every button label starts with a verb and no row text exceeds 60 characters.
- [ ] **Task 3: Protocol and reducer.** Event and command types; the reducer; `view.ts`. Tests: one test per state of 9.3 reached from events; approvals, help requests, dialogs, tabs, blocked navigation, end of session, reconnect history; a typing step carries a count, never text.
- [ ] **Task 4: Timeline.** Rows from steps: sentence per tool (9.7), consecutive reads collapsed with a count, idle dividers after `viewer.idle_divider_s`, durations. Tests for each rule.
- [ ] **Task 5: Recorded sessions and the demo connection.** `Connection` interface; the demo player (real pace and stepped), which answers commands the way the service will (approve, deny, pause, resume, take over, hand back, done, could not, stop); the state fixtures; the recorded pictures. Tests: the player emits in order, waits at an approval, times out to denied, and stops on Stop.
- [ ] **Task 6: Shell and live frame.** App layout (split, full, stacked), top bar, tab strip, address bar, live frame on a canvas with its text alternative, control border and label, target highlight and agent pointer, status line, counters. Tests: each state shows its label and controls; the frame's alternative text follows the page.
- [ ] **Task 7: Controls and cards.** Pause or Resume, Take over or Hand back, Stop with confirmation; approval card with time left; help card; dialog card; takeover bar; toasts; notice panel; summary card. Tests: each button sends its command; an approval does not steal focus; Stop asks first; no answer shows as denied.
- [ ] **Task 8: Timeline panel and step drawer.** The log region, rows, idle dividers, selection, the drawer with the step's picture, target, timing and raw result. Tests: new rows are announced without moving focus; Up and Down move, Enter opens.
- [ ] **Task 9: Settings screen.** Drawn from the settings answer; groups, rows, controls (choice, switch, list, action, read-only); saved and refused states; locked rows; next-session note; phone layout; Clear browsing data confirmation; About. Tests: the web, mobile and desktop sets show exactly their settings; a locked row is disabled and says why; a refused change puts the control back.
- [ ] **Task 10: Keyboard, announcements, themes, motion.** The keyboard map of 9.8; live regions per 9.3; theme from the setting and the system; reduced motion. Tests: each key does its action only when allowed; each state change is announced with the right urgency.
- [ ] **Task 11: End-to-end checks.** `tests/viewer/`: build the viewer, open every state in both themes at desktop and phone width, no console errors, no sideways scroll, axe has no violations, keyboard walk-through; screenshots saved for review. Verify: `uv run pytest tests/viewer -q`.

## Verification for the whole plan

```bash
npm --prefix viewer run typecheck
npm --prefix viewer run lint
npm --prefix viewer run test
npm --prefix viewer run build
uv run pytest tests/viewer -q
```

Then open the built viewer at `?demo=signup` and walk the run by hand: watch, approve, deny, pause, take over, hand back, stop, settings in both themes and at phone width.
