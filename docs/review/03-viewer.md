# Viewer audit: spec §9, §4.8 (client side), §15.19 against `viewer/` code

Read-only. Nothing was modified, and `.env` was not read.

**How to read the evidence.** Paths are relative to `/Users/sharan/Downloads/Prj-Browser/viewer/src/` unless they start with `tests/` or `viewer/`. Short names used below:

| Short name | File |
|---|---|
| `App` | `App.tsx` |
| `view` | `state/view.ts` |
| `reducer` | `state/reducer.ts` |
| `timeline.ts` | `state/timeline.ts` |
| `socket` | `connection/socket.ts` |
| `BrowserPane`, `StatusPanel`, `Cards`, `Timeline`, `SettingsScreen`, `focus.ts` | files in `components/` |
| `W` | `wording.ts` |
| `app.css`, `settings.css`, `base.css` | files in `styles/` |
| `demo/settings.ts`, `demo/sessions.ts` | recorded data |

**Unverified.** I ran no tests and rendered nothing, because an install was running. Every verdict comes from reading code and tests. Claims such as "axe clean" and "no sideways scroll" rest on tests existing, not on a run. Whether the Python service builds the §9.7 sentences correctly was not checked. The two behaviour findings marked "(from reading)" were not reproduced.

**Three facts that colour everything else**

1. **A live session's settings screen offers only two settings.** These are "Show where the agent is acting" and "Colour mode" (`main.tsx:19,53`). They are kept in memory and lost on reload. The other 20 exist only in the in-viewer stand-in `demo/settings.ts`, reachable with `?demo=` or `?state=`. The service has no settings API; its routes are `/api/sessions` and the WebSocket only (`src/bap_browser/service/app.py:103-104`).
2. **The viewer never receives its `viewer.*` options from the service.** Stale-after 5 s, idle divider 10 s, release chord and toast 4 s are constants in `options.ts:17-23`.
3. **An unknown event type breaks the viewer (from reading).** `socket.ts:149` forwards any JSON with a `type`, and `reducer.ts:158-273` has no default case, so the state becomes `undefined` and the next render throws. `bridge_changed` from a milestone 2 service would do this. There is no error boundary.

---

## 1. Tables

### 9.1 Principles

| Ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 9.1-1 | Who is driving, in words and an icon | BUILT | `BrowserPane:236-243`, `StatusPanel:14-25` | None |
| 9.1-2 | One plain sentence for what is happening now | BUILT | `view:37-41,144-152` | None |
| 9.1-3 | Stop, pause, take over one action away | BUILT | `StatusPanel:69-113`, `App:303-307` | Covered by the settings dialog while it is open (see 9.12 rule 9) |
| 9.1-4 | Every step has a picture and its result | PARTIAL | `Timeline:125-155`, `socket:169-172` | Steps replayed from history have no picture; the "result" is the sentence, not a raw result |
| 9.1-5 | Approval states what, where and why; no answer means no | PARTIAL | `Cards:24-43`, `W:68` | "Why" is not shown. `site` and `tool` are stored but unused (`W.approval.on` has 0 uses); "where" appears only if the summary sentence contains it |
| 9.1-6 | Calm: no looping animation, no glow | BUILT | `base.css:160-171`, `app.css:244` | None |
| 9.1-7 | Keyboard and screen reader first-class | PARTIAL | `App:179-204,374-379` | No off switch for single-letter keys; focus is lost after some buttons (see 9.9) |
| 9.1-8 | Honest about state | BUILT | `view:43-55,65-85` | None |

### 9.2 Layout

| Ref | Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|---|
| 9.2 | Split view by default | BUILT | `App:258,324-331`, `app.css:94-101` | None |
| 9.2 | Top bar: name, session, agent, browser, settings, connection | PARTIAL | `App:259-301` | Session is a static chip, not a picker. Below 700 px the session chip and connection text are hidden (`app.css:1009-1013`) |
| 9.2 | Full view during takeover, with the takeover bar | BUILT | `App:116-118`, `StatusPanel:65-67` | None |
| 9.2 | Below 980 px columns stack, browser first | BUILT | `app.css:963-973` | None |
| 9.2 | Never scrolls sideways; 16 px gutter | BUILT | `app.css:18,100`; `tests/viewer/test_states.py:41` | Not run |
| 9.2 | The look: edgeless top bar, pills, one browser card, warm stage, warm activity panel with white cards | BUILT | `app.css:12-55,109-118,249-259,430-452` | Waiting and danger cards use tints, not white |
| 9.2 mock | Tabs drawn with a close "x" | DIFFERS | `BrowserPane:36-50` | Tabs have no close control; the component table only asks "click to view one" |
| 9.2 | `?surface=web/mobile/desktop`, web by default, decides the settings set | BUILT | `main.tsx:22-23` | Only matters in recorded mode (fact 1) |
| 9.2 | Inside a client the product name is dropped | BUILT | `App:260-267`, `main.tsx:61` | Triggered by `?embed`, not detected from framing |
| 9.2 | Phone: watch, read, approve, pause, stop, take over, hand back | BUILT | `app.css:963-1041`; `tests/viewer/test_states.py:32-42` | Not run |
| 9.2 | Phone: taps and drags on the picture go to the page | PARTIAL | `BrowserPane:196-198` | No `touch-action`, pointer capture or `pointercancel` handling in `src`, so a drag scrolls the viewer (status M19 says the same) |
| 9.2 | Take-over Chrome: no picture, tabs and address shown | BUILT | `view:48`, `BrowserPane:130-140` | Built ahead of milestone 2 |

### 9.3 States

| State | Verdict | Evidence | Missing / different |
|---|---|---|---|
| No agent yet | BUILT | `view:68-70`, `BrowserPane:130-140` | Also shown while the socket is connecting or reconnecting before any `session_started`, because the session check (`view:68`) comes before the connection check (`view:83`) |
| Agent | BUILT | `view:144-152`, `StatusPanel:127-131`, `App:213` | None |
| Waiting for approval | BUILT | `view:88-97`, `App:206-207` | None |
| Person requested | BUILT | `view:98-107` | The reason is on the detail line, not joined to the title with ": " |
| Person | BUILT | `view:108-118` | None |
| Paused | BUILT | `view:119-128`, `app.css:294-296` | The badge still says "Live" |
| Blocked | BUILT | `view:133-143`, `Cards:74-85` | Only while control is `agent`, until the next `step_started` (`reducer:186`) |
| Ended | BUILT | `view:72-82`, `BrowserPane:181,229`, `Cards:99-119` | "Why" is in the summary card only (`StatusPanel:67`) |
| Disconnected | BUILT | `view:83-85`, `BrowserPane:94-99` | None |
| Link refused | BUILT | `view:65-67,44`, `BrowserPane:136`, `socket:113-116` | Close code 4404 is treated the same |
| Stale picture | BUILT | `view:53`, `BrowserPane:85-91` | Threshold hard-coded (fact 2); shows the real seconds |
| Browser not connected (M2) | NOT BUILT | No `bridge_changed` in `protocol.ts:31-56`; no wording | Expected at milestone 2 |

**The status page's seven "not built" items: all seven confirmed.**

| Item | What the code shows |
|---|---|
| Session picker | `W.topBar.sessions` has 0 uses; `App:270-273` is a static chip; the session comes from `?session=` (`main.tsx:48`) |
| Settings "saving" | `W.settings.saving` has 0 uses |
| Control buttons "working" | `Button` has a `disabled` prop that `StatusPanel` never sets; a control that does not apply is hidden, not disabled |
| Takeover bar "handing back" | `App:164-167` sends `hand_back` and shows the toast at once, before any confirmation |
| Takeover bar "failed" | No such state anywhere |
| Address "loading" | `BrowserPane:60-72` has only loaded and blocked |
| Notice "limit reached" | No card and no wording |

### 9.4 Components

| Component | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Top bar | PARTIAL | `App:259-301`, `W:167-173` | No session picker; no separate "disconnected" wording (connecting, reconnecting, "Not connected") |
| Settings screen | PARTIAL | `SettingsScreen:145-147,68-70` | Loading, ready, saved, refused present. "Saving" absent. An extra "could not be loaded" state |
| Setting row | PARTIAL | `SettingsScreen:217-325` | "Applies to the next session" appears only after a save, not as a standing state |
| Browser picker (M2) | NOT BUILT | — | Only a one-choice "Preferred browser" in the stand-in (`demo/settings.ts:18-29`) |
| Session picker | NOT BUILT | — | See above |
| Tab strip | BUILT | `BrowserPane:35-51`, `app.css:128-170` | Attention is a colour dot with a screen-reader label only; no arrow-key movement in the tab list |
| Address bar | PARTIAL | `BrowserPane:60-72` | No "loading" |
| Live frame | BUILT | `view:21,43-55`, `BrowserPane:107-234` | All seven states, plus `own_browser` and `empty` |
| Control border and label | BUILT | `app.css:278-296,330-352`, `BrowserPane:12-19` | None |
| Target highlight and pointer | PARTIAL | `BrowserPane:177-228`, `app.css:368-398` | "Targeting" only; no "acted" state |
| Target drawn by the viewer, nothing injected | BUILT | `BrowserPane:206-227` | DOM layer over the canvas |
| Status line | BUILT | `StatusPanel:116-132` | None |
| Control buttons | PARTIAL | `StatusPanel:69-113` | No "disabled", no "working" |
| Approval card | PARTIAL | `Cards:24-43`, `App:54-59,146,251` | Pending only. Allowed, denied and expired are toasts after the card goes. The unwatched card is built |
| Help card | PARTIAL | `Cards:46-57` | Requested and person-active look the same; done, could not, timed out are toasts |
| Dialog card | PARTIAL | `Cards:60-72`, `reducer:241-245` | Open only. The outcome is ignored and no time left is shown |
| Takeover bar | PARTIAL | `StatusPanel:65-67`, `app.css:546-549` | Active only |
| Timeline | BUILT | `Timeline:22-90` | Not shown in full view |
| Timeline row | BUILT | `Timeline:50-79`, `app.css:686-758` | None |
| Idle divider | BUILT | `timeline.ts:34-36`, `Timeline:46-48` | None |
| Step drawer | PARTIAL | `Timeline:98-158` | Picture, target, timing, address present. No raw result (the protocol has none). Split view only |
| Summary card | BUILT | `Cards:99-119`, `W:57-62` | Files is a count, not a list |
| Notice panel | PARTIAL | `Cards:74-85` | Blocked page has a next action. Lost connection is a status line with no next action. Limit reached is absent |
| Counters | BUILT | `Timeline:85-87` | None |
| Toast | DIFFERS | `App:139-144,334-343` | Only the newest toast has a timer, so an older one stays 4 s after the newer one leaves (status M16). Also used for service notices, not only the person's own actions |

### 9.5 Design tokens

**Colour.** Every name and value matches the spec in both themes. Light is `tokens.css:27-48`; dark is `tokens.css:125-146` (system) and `155-176` (chosen).

| Token | Light | Dark | Verdict |
|---|---|---|---|
| `--bg` | #FFFFFF | #151515 | BUILT |
| `--surface` | #FFFFFF | #242424 | BUILT |
| `--surface-2` | #F5F4F2 | #1E1E1E | BUILT |
| `--surface-3` | #ECEAE7 | #2C2C2C | BUILT |
| `--border` | rgb(17 17 17 / 0.12) | rgb(233 235 223 / 0.12) | BUILT |
| `--border-strong` | #8D8881 | #94958E | BUILT |
| `--text` | #1A1714 | #E9EBDF | BUILT |
| `--text-muted` | #56524D | #CBCCC4 | BUILT |
| `--ink` / `--on-ink` | #09090B / #FFFFFF | #EBEBEB / #111111 | BUILT |
| `--focus` | #1A1714 | #E9EBDF | BUILT |
| `--agent` / tint | #6E3B83 / #F6EFF9 | #D4B4E6 / #392F3E | BUILT |
| `--person` / tint | #1D4ED8 / #EAF2FF | #93C5FD / #2B333E | BUILT |
| `--waiting` / tint | #8A5200 / #FFF4DB | #FCD34D / #3E3724 | BUILT |
| `--danger` / tint | #BF2B37 / #FFF2F3 | #FCA5A5 / #3D2D2D | BUILT |
| `--success` / tint | #137A43 / #EAF8F0 | #86EFAC / #293A2F | BUILT |
| `--brand-gradient` | #EC3B4B, #BE3B5F, #A03B6C, #6E3B83 | #FF5A64, #E0567E, #C25792, #9A63B4 | BUILT |

| Rule or token | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Contrast 4.5:1 text, 3:1 controls; lowest 4.91:1 | BUILT | `tokens.test.ts:43-86` | Test not run |
| Red means only blocked, failed, stop | DIFFERS | `Cards:38`, `SettingsScreen:315`, `settings.css:312-314` | Deny, "Clear data" and a refused setting's message are also red |
| Theme follows the system and can be set | PARTIAL | `tokens.css:122-180`, `App:107-112` | Works, but the choice is in memory and lost on reload |
| Gradient only on the brand mark and an "on" switch | BUILT | `app.css:38`, `settings.css:224` | None |
| `--font-ui` Hanken Grotesk, shipped as two files with the licence | BUILT | `tokens.css:5-21,53`, `fonts/OFL.txt` | None |
| `--font-mono` system monospace | BUILT | `tokens.css:54` | None |
| Sizes 12, 13, 14, 16, 18 | BUILT | `tokens.css:55-59` | None |
| Weights 400, 500, 600 | BUILT | `tokens.css:60-62` | None |
| Line height 1.45, 1.3 titles | BUILT | `tokens.css:63-64` | Buttons use a written-out `line-height: 1` (`base.css:97`) |
| Spacing 4, 8, 12, 16, 24, 32 | BUILT | `tokens.css:69-74` | A derived 6 px at `app.css:191` |
| Radius 4, 10, 16, 20, pill | BUILT | `tokens.css:77-81` | Toast uses 16; the live frame uses 10 |
| Border 1 px; 3 px around the frame | BUILT | `tokens.css:82-83`, `app.css:271` | None |
| Shadow only under what floats | BUILT | `tokens.css:86`, `app.css:274,803,902,946`, `settings.css:11` | Also on the frame label (`app.css:324`) |
| Duration 150 and 200 ms | BUILT | `tokens.css:89-90` | 150 ms is used once, on the switch knob |
| Easing cubic-bezier(0.22, 1, 0.36, 1) | BUILT | `tokens.css:92` | None |
| Focus ring 2 px solid, 2 px offset | BUILT | `tokens.css:95-96`, `base.css:53-56` | Tabs and rows draw it inside |
| Buttons 36 px; nothing under 32 × 32 | BUILT | `tokens.css:97-98`, `base.css:88-89`, `app.css:133,691` | Rendered sizes not measured |
| Tokens live in `tokens.css` | BUILT | `tokens.css` | None |
| Only token values are used | PARTIAL | `styles.test.ts:19-37` | See below |

**Do styles use tokens only?** For colours, pixel sizes, durations and font names, yes: `styles.test.ts` refuses any written out in the three stylesheets. Values the test cannot see:

- Opacities 0.5, 0.9 and 0.35 (`base.css:107,141,169`).
- `color-mix` at 14% (`app.css:373,380,385`).
- `line-height: 1` (`base.css:97`).
- An inset ring shadow (`settings.css:163`) and a `drop-shadow` (`app.css:397`), both built from tokens.
- Bare z-index numbers, 50% radii and widths, and the 1.6 and 16/10 ratios (`app.css:401-402`).
- The 979 px and 699 px breakpoints.

`tokens.css` also holds about 30 tokens the spec does not list (see section 2).

### 9.6 Wording

| Where | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Rule: sentence case | BUILT | `W` throughout | "Live" and the panel title are upper-cased by CSS |
| Rule: buttons start with a verb | BUILT | `W:34-56` | "Back" is not a verb; "Done" is the spec's own |
| Rule: say what will happen | BUILT | `W:68,86,113-114` | None |
| Rule: no jargon | PARTIAL | `Timeline:119`, `W:137` | The drawer shows tool names such as `browser_click`; the counters say "chars" |
| Rule: a row under 60 characters | PARTIAL | `demo/sessions.test.ts:91` | Checked for the recording only; the viewer shows whatever the service sends |
| Status | BUILT | `W:9-16` | None |
| Buttons | BUILT | `W:35-42` | None |
| Approval | BUILT | `W:43-45` | None |
| Approval title | BUILT | `W:66`, `Cards:29-31` | None |
| Takeover bar | BUILT | `W:107` | None |
| Hand-back toast | BUILT | `W:108` | None |
| Stop confirmation | BUILT | `W:113-114` | Split into question and consequence; the safe button is "Keep running" |
| Time limit on a card | BUILT | `W:68` | None |
| Nobody was watching | BUILT | `W:74` | None |
| Disconnected | BUILT | `W:17` | None |
| Link refused (four strings) | BUILT | `W:18,21,125,172` | None |
| Empty timeline | BUILT | `W:132` | None |
| Browser names | BUILT | `W:187-189` | None |
| "Settings" and the eight group names | BUILT | `W:193`, `demo/settings.ts:14` | Group names live in the stand-in, not in `wording.ts` |
| Saved change | BUILT | `W:195-196` | None |
| Locked setting | BUILT | `W:198` | None |
| Clear browsing data | BUILT | `W:213-214,48-49`, `demo/settings.ts:229-233` | The copy on screen is the stand-in's; the `W` copies have 0 uses |
| Site prompt in own browser (M2) | NOT BUILT | — | "Always allow on this site" and "Don't allow" absent |
| Preview of a consequential action (M2) | NOT BUILT | — | Absent |
| Browser not connected (M2) | NOT BUILT | — | Absent |
| Every human-readable string is in `wording.ts` | PARTIAL | See below | — |

**Strings outside `wording.ts`.** The status page's count of seven is right for literal interface strings:

| # | String | Where |
|---|---|---|
| 1 | "Activity" | `App.tsx:325` |
| 2 | "Steps" | `components/Timeline.tsx:43` |
| 3 | "Elapsed " | `components/StatusPanel.tsx:129` |
| 4 | "Browser" | `components/BrowserPane.tsx:34` |
| 5 | "Browser tabs" | `components/BrowserPane.tsx:36` |
| 6 | "needs attention" | `components/BrowserPane.tsx:47` |
| 7 | "Address" | `components/BrowserPane.tsx:66` |

Not in that count:

- Unit text in `state/timeline.ts:62-84`: "under 1 ms", "ms", "s", "B", "KB", "MB".
- The `about:blank` fallback (`BrowserPane:61`).
- Every setting title, description and choice label (`demo/settings.ts:17-303`).

Nine `W` keys have no use: `topBar.sessions`, `settings.saving`, `buttons.viewStep`, `settings.listEmpty`, `frame.blockedPage`, `help.title`, `timeline.stepNumber`, `approval.on`, `buttons.clearData`, plus the `settings.clear.question` and `consequence` pair.

### 9.7 Timeline rows

The viewer does not build sentences from the tool. It shows `label` while a step runs and `summary` once it finishes (`timeline.ts:51`). "BUILT" here means the row is shown as sent.

| Tool or rule | Verdict | Evidence | Missing / different |
|---|---|---|---|
| `browser_navigate` | BUILT | `demo/sessions.ts:70` | None |
| `browser_click` | BUILT | `demo/sessions.ts:95-96` | None |
| `browser_type` | BUILT | `demo/sessions.ts:73-74` | None |
| `browser_fill_form` | BUILT | Pass-through only | No recording or test in the viewer; unverified |
| `browser_snapshot`, `browser_get_text` | BUILT | `timeline.ts:6`, `demo/sessions.ts:72,98-99` | None |
| `browser_find` | BUILT | Pass-through only | No example; unverified |
| `browser_screenshot` | BUILT | Pass-through only | No example; unverified |
| `browser_scroll` | BUILT | Pass-through only | No example; unverified |
| `browser_upload_file` | BUILT | `demo/sessions.ts:82,89` | None |
| `browser_run` expands to its steps (M4) | NOT BUILT | — | No expandable row |
| `browser_request_human` | BUILT | `demo/sessions.ts:100,108` | None |
| A failed step | BUILT | `Timeline:66-71`, `app.css:751-754` | Icon, the word "Failed", red text |
| Typed text as a count, never the text | BUILT | `reducer.test.ts:110`, `demo/sessions.test.ts:85` | The viewer cannot enforce it; it relies on the service |
| Consecutive reads collapse with a count | BUILT | `timeline.ts:26-44`, `Timeline:64` | Shows the first step's number, opens the newest (status M18) |
| Idle divider at `viewer.idle_divider_s` | PARTIAL | `timeline.ts:34-36`, `options.ts:19` | Works; the threshold is a constant, not read from the service |
| Each row shows its duration and opens the drawer | BUILT | `Timeline:59,77` | A running row shows "Running" |

### 9.8 Keyboard

| Key | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Tab, Shift+Tab in visual order | BUILT | `tests/viewer/test_walkthrough.py:122-139` | Not run |
| P | BUILT | `App:193-195` | Off while settings, the stop question or the drawer is open |
| T | BUILT | `App:196-197` | Works when the agent drives or the page is blocked; not when paused or help is requested, though the button is offered there |
| A | BUILT | `App:186-191,148-150` | For help it focuses the card, not a button. Does nothing while the drawer is open or focus is in a settings control (status M17) |
| Enter, Space | BUILT | Native buttons | None |
| Up, Down; Enter opens the drawer | BUILT | `Timeline:30-37,58` | None |
| F | BUILT | `App:198-199` | Still toggles below 980 px, where the matching button is hidden |
| Ctrl+Alt+Enter leaves the frame | PARTIAL | `BrowserPane:155-159`, `App:322`, `options.ts:20,26-37` | Works; the chord is a constant, not read from `viewer.takeover.release_chord` |
| During takeover every other key goes to the page | DIFFERS | `BrowserPane:160-165` | Tab is never sent, so a person cannot tab between the page's fields. Keys reach the page only once the picture has focus, and focus is not moved there on takeover |
| Stop always asks | BUILT | `App:222,356-372` | The safe answer has the focus |

### 9.9 Accessibility

| Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Target: WCAG 2.2 AA | PARTIAL | `tests/viewer/test_states.py:42`, `tests/viewer/conftest.py:74-83` | axe runs on every state, theme and size (not run by me). Criterion 2.1.4 is not met |
| Every control reachable, visible focus ring | BUILT | `base.css:53-56`, `tests/viewer/test_walkthrough.py:122-139` | None |
| Live regions: immediate for approvals, help, takeover, blocks; polite for the rest | BUILT | `App:206-213,374-379`, `view` urgency | Each step changes the polite region twice (status M20) |
| Live frame text alternative kept current | BUILT | `W:118`, `BrowserPane:190-191` | None |
| Timeline is a log region | BUILT | `Timeline:43` | New steps are also sent to the polite region |
| An approval does not steal focus; A moves to it | BUILT | `App:186-191` | None |
| Dialog keeps Tab inside; focus never goes nowhere | PARTIAL | `focus.ts:12-25`, `App:244,365`, `SettingsScreen:103-110` | Trap and three hand-offs are built. From reading: no focus move after Pause, Resume, Take over, Hand back, Done or Couldn't do it, whose buttons are removed (`StatusPanel:69-113`), nor after cancelling the clear-data question (`SettingsScreen:201`) |
| Every state has an icon and a label as well as colour | BUILT | `StatusPanel:14-25`, `BrowserPane:12-19`, `settings.css:232-238` | The tab attention dot is colour only to the eye |
| 200% zoom reflows to one column | BUILT | `tests/viewer/test_states.py:83-101` | Not run |
| Off switch for single-letter keys (WCAG 2.1.4, level A) | NOT BUILT | `App:179-204` | P, T, A and F act at once from anywhere outside a text field. No setting, remap or disable exists; nothing in the settings catalogue or `options.ts` |

### 9.10 Motion

| Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Only opacity and transform, at most 200 ms | BUILT | `base.css:160-165`, `settings.css:218`; `tests/viewer/test_walkthrough.py:177-188` | None |
| Only repeating motion is the "live" dot, once a second | BUILT | `app.css:244`, `tokens.css:91` | None |
| No animated shadows or glows | BUILT | No shadow in any keyframe or transition | None |
| Reduced motion: nothing animates, dot steady | BUILT | `base.css:173-180`; `tests/viewer/test_walkthrough.py:161-174` | None |

### 9.11 Viewer build

| Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|
| One reducer fed by the event stream | BUILT | `reducer:134-146`, `App:69` | Breaks on an unknown event (fact 3) |
| `demo/` holds events, settings and a picture per step | BUILT | `demo/sessions.ts`, `demo/settings.ts`, `demo/frames/` (9 pictures), `viewer/scripts/record_demo.py` | None |
| `?demo=<name>` at real pace | BUILT | `main.tsx:26-30` | One recording, `signup`; `?pace=` scales it |
| `?demo` stepped by hand | NOT BUILT | — | No stepping control |
| `?state=<name>` opens one state | BUILT | `demo/sessions.ts:150-179` | 15 recordings. None for "refused" or the unwatched card. An unknown name plays the signup run without saying so (`main.tsx:29`) |
| Frames drawn on a canvas, target and pointer on a layer above | BUILT | `BrowserPane:115-128,206-227` | None |
| While an approval waits, the element stays outlined in the waiting colour | BUILT | `BrowserPane:178-179`, `app.css:378-391` | None |
| Full view: status bar above, what needs a person between bar and browser | BUILT | `App:303-312`, `app.css:531-569` | None |
| Takeover: positions scaled to page pixels; `pointer`, `wheel`, `key` sent | BUILT | `BrowserPane:144-175` | Proven against the real service in `tests/viewer/test_live_session.py:77-90` (not run) |
| `npm run build` writes into `src/bap_browser/viewer_dist/` | BUILT | `viewer/vite.config.ts:10` | None |

### 9.12 Settings screen

**Layout**

| Requirement | Verdict | Evidence |
|---|---|---|
| Opened from the top bar button | BUILT | `App:298,345-354` |
| Dialog: groups left, settings right | BUILT | `SettingsScreen:122-193`, `settings.css:37-42` |
| Below 700 px: a list, then a screen with Back | BUILT | `settings.css:347-401`, `SettingsScreen:30,98-110,174` |

**Each setting.** "Stand-in" means `demo/settings.ts`. "Live" means a real session.

| Spec setting | In the stand-in (surfaces) | Offered live | Verdict | Missing / different |
|---|---|---|---|---|
| Preferred browser | web, desktop (`:18`) | No | PARTIAL | One choice only; no backend |
| Stay signed in to sites | all (`:30`) | No | PARTIAL | No backend |
| My Chrome | desktop only (`:41`) | No | DIFFERS | The spec has it on web too. Shown though milestone 2 is not built |
| Show the built-in browser | desktop (`:53`) | No | PARTIAL | Shown though milestone 3 is not built |
| Ask before | all (`:68`) | No | PARTIAL | No backend |
| Wait for my answer | all (`:83`) | No | PARTIAL | No backend |
| Remember "Allow on this site" | all (`:100`) | No | PARTIAL | A two-option select, not the mock's checkbox |
| In my Chrome | desktop only (`:115`) | No | DIFFERS | The spec has it on web too |
| Blocked sites | all (`:130`) | No | PARTIAL | No backend |
| Only allow these sites | all (`:142`) | No | PARTIAL | No backend |
| Approved sites | desktop only (`:153`) | No | DIFFERS | The spec has it on web too |
| Let the agent download files | all (`:164`) | No | PARTIAL | No backend |
| Let the agent upload files | all (`:175`) | No | PARTIAL | No backend |
| Download folder | desktop (`:186`) | No | PARTIAL | The button does nothing |
| Folders the agent may upload from | desktop (`:198`) | No | PARTIAL | The button does nothing |
| Keep a log of the agent's steps | all (`:210`) | No | PARTIAL | No backend |
| Clear browsing data | all (`:221`) | No | PARTIAL | Asks first, but `run` does nothing (`:354`) and the toast still says "Browsing data cleared." |
| Picture quality | all (`:238`) | No | PARTIAL | No effect |
| Show where the agent is acting | all (`:254`) | **Yes** | BUILT | Works at once (`App:34,319`); in memory |
| Colour mode | all (`:265`) | **Yes** | BUILT | Works at once (`App:107-112`); lost on reload |
| Notify me when the agent needs me (next) | absent | No | NOT BUILT | Expected |
| Let the agent run scripts in pages | web, desktop (`:281`) | No | PARTIAL | The stand-in's locked example |
| About this deployment | web, desktop (`:292`) | No | PARTIAL | Values are made up (`:356-365`) |

Stand-in totals: web 16, mobile 13, desktop 22.

**Rules**

| Rule | Verdict | Evidence | Missing / different |
|---|---|---|---|
| Drawn from the settings API; the viewer holds no list | DIFFERS | `main.tsx:53`, `demo/settings.ts:17-303` | No settings API client exists. The screen is generic over `SettingsSource` (`settings/types.ts:59-65`), but the only source is the catalogue inside the viewer |
| Saved at once, no Save button, "Saved" for a moment | BUILT | `SettingsScreen:58-73` | The word stays until the next change or group switch |
| Locked: value shown, disabled, "Set by your organisation" | BUILT | `SettingsScreen:222-226,239,289,304` | None |
| Site list saved on blur and on close; a refused entry keeps the screen open | BUILT | `SettingsScreen:83-95,353-355`; `App.test.tsx:666-696` | None |
| A refused change is put back with the reason; a site list keeps what was typed | BUILT | `SettingsScreen:69-71,329` | None |
| Deployment's entries above the box, marked, not removable | BUILT | `SettingsScreen:333-342` | Marked by a lock icon and a screen-reader label; no visible words |
| One site per line; a bad entry refused in the row | BUILT | `W:206,208`, `demo/settings.ts:15,316-318` | The check is in the stand-in |
| Clear browsing data asks first | BUILT | `SettingsScreen:186,194-203` | Recorded mode only |
| Opening does not pause; Stop, pause, approvals stay reachable | PARTIAL | `App:186-192` | An approval is announced and A closes the screen and moves to it. Stop and Pause sit behind the modal and P is off, so they are one Escape away |
| Up and Down between groups, Tab within, Escape closes, focus returns to the button | BUILT | `SettingsScreen:112-120,131-136`, `App:152-157` | None |
| About: version, browser, changed values with source, copy as text | PARTIAL | `SettingsScreen:364-422` | The screen is built; data is made up and absent live. "Copied." shows even without a clipboard (status M16) |

### 9.13 Later in the viewer

| Item | Verdict | Evidence |
|---|---|---|
| Sign-in form | NOT BUILT | Nothing in `src` |
| Replay player | NOT BUILT | Nothing |
| Notifications | NOT BUILT | Nothing |
| A note to the agent | NOT BUILT | Nothing |
| Typing with a phone's on-screen keyboard | NOT BUILT | Nothing |
| Plan card | NOT BUILT | Nothing |

All six are expected: the spec marks them Next or Later.

### 4.8 Viewer protocol, client side

**Connection**

| Requirement | Verdict | Evidence | Missing / different |
|---|---|---|---|
| One WebSocket per viewer and session | BUILT | `socket:98-99`, `connection/address.ts:32-36` | None |
| First message carries the token | BUILT | `socket:107`; `connection/socket.test.ts:101-115` | None |
| Binary = one type byte + JPEG | BUILT | `socket:125-128` | Other type bytes are ignored |
| Replay order handled | BUILT | `socket:133-149`, `reducer:139-143,160-177` | None |
| A lost connection keeps the pictures it had | BUILT | `socket:59,169-172` | Retries after 0.5, 1, 2, 5 s |
| Close 4401: no retry, "link can't open the session" | BUILT | `socket:36,113-116` | None |

**Service to viewer**

| Message | Verdict | Evidence | Missing / different |
|---|---|---|---|
| `session_started` | BUILT | `reducer:160-177` | `browser` shown only as a hover title |
| `control_changed` | BUILT | `reducer:179-180` | None |
| `step_started` | BUILT | `reducer:182-187` | None |
| `step_finished` | BUILT | `reducer:189-205`, `socket:143-147` | None |
| `tab_changed` | BUILT | `reducer:207-210` | None |
| `approval_requested` | BUILT | `reducer:212-223` | `tool` and `site` stored, not shown |
| `approval_closed`, incl. `unwatched` | BUILT | `reducer:225-228`, `App:59,146,251` | None |
| `help_requested` | BUILT | `reducer:230-234` | None |
| `help_closed` | BUILT | `reducer:236-239` | None |
| `dialog_opened` | PARTIAL | `reducer:241-242` | `expires_in_s` stored, never shown |
| `dialog_closed` | PARTIAL | `reducer:244-245` | `outcome` ignored |
| `download_saved` | BUILT | `reducer:247-251`, `App:62-63` | None |
| `picture_current` | BUILT | `reducer:259-260` | None |
| `caught_up` | BUILT | `socket:134-138`, `reducer:141-142` | None |
| `navigation_blocked` | BUILT | `reducer:253-254` | None |
| `settings_changed` | PARTIAL | `reducer:256-257`, `SettingsScreen:39-48` | Re-reads settings only while the screen is open; `changes` ignored; theme and pointer not refreshed. The service emits none (grep of `src/bap_browser`) |
| `bridge_changed` (M2) | NOT BUILT | Not in `protocol.ts:31-56` | Would break the viewer (fact 3) |
| `session_ended` | BUILT | `reducer:262-272` | None |
| frame | BUILT | `socket:152-166`, `BrowserPane:115-128` | None |

**Viewer to service.** All 14 are sent.

| Message | Verdict | Evidence |
|---|---|---|
| `auth` | BUILT | `socket:107` |
| `approve` (scope `once` or `site`) | BUILT | `App:242` |
| `deny` | BUILT | `App:242` |
| `pause` | BUILT | `StatusPanel:73`, `App:194` |
| `resume` | BUILT | `StatusPanel:79`, `App:195` |
| `stop` | BUILT | `App:364` |
| `take_over` | BUILT | `StatusPanel:85`, `App:197` |
| `hand_back` | BUILT | `App:165` |
| `done` | BUILT | `StatusPanel:97` |
| `could_not` | BUILT | `StatusPanel:103` |
| `pointer` | BUILT | `BrowserPane:150-152` |
| `key` | BUILT | `BrowserPane:153-172` |
| `wheel` | BUILT | `BrowserPane:173-175` |
| `select_tab` | BUILT | `BrowserPane:44` |

A command sent while the socket is not open is dropped without a word (`socket:75-77`).

**The three honesty rules, and take-over Chrome**

| Requirement | Verdict | Evidence |
|---|---|---|
| Stale only when neither a picture nor `picture_current` arrived | BUILT | `reducer:259-260`, `view:53` |
| Nothing before `caught_up` is toasted as new; a later step keeps its picture | BUILT | `reducer:148-151`, `socket:169-172` |
| An `unwatched` approval stays as a card until dismissed | BUILT | `App:146,251`, `Cards:88-97` |
| Take-over Chrome with no frames still works | BUILT | `view:48`; `App.test.tsx:149` |

### 15.19 Viewer feature rows

| ID | Feature | Verdict | Missing / different |
|---|---|---|---|
| UI-01 | Design tokens, light and dark | BUILT | None |
| UI-02 | Split and full view | BUILT | None |
| UI-03 | Session picker with state badges | NOT BUILT | Static chip only |
| UI-04 | Live frame over a binary WebSocket | BUILT | None |
| UI-05 | Tab strip and address bar | PARTIAL | No "loading" address state |
| UI-06 | Control border and label | BUILT | None |
| UI-07 | Status line with action and elapsed time | BUILT | None |
| UI-08 | Target highlight and agent pointer | BUILT | No "acted" state |
| UI-09 | Timeline rows, typing collapsed, idle gaps | BUILT | None |
| UI-10 | Step drawer with picture and raw result | PARTIAL | No raw result |
| UI-11 | Approval card | BUILT | None |
| UI-12 | Pause, resume, stop | BUILT | None |
| UI-13 | Take over and hand back with remote input | PARTIAL | Tab not forwarded; hand-back not confirmed; phone drag |
| UI-14 | Help card, Done or Couldn't do it | BUILT | None |
| UI-15 | Dialog card | PARTIAL | Open state only |
| UI-16 | Blocked, ended, disconnected, refused, stale | BUILT | None |
| UI-17 | Keyboard, announcements, reduced motion | PARTIAL | No 2.1.4 switch; focus lost after some buttons |
| UI-18 | Summary card and counters | BUILT | None |
| UI-19 | Autonomy mode switch, in settings | PARTIAL | "Ask before" is in the stand-in only |
| UI-20 | Sign-in form (Next) | NOT BUILT | Expected |
| UI-21 | Replay player (Next) | NOT BUILT | Expected |
| UI-22 | Site permissions and browser-data settings | PARTIAL | Stand-in only; clearing does nothing |
| UI-23 | Notifications (Next) | NOT BUILT | Expected |
| UI-24 | A note to the agent (Next) | NOT BUILT | Expected |
| UI-25 | Read-only view of effective settings | PARTIAL | The "About" screen with made-up data |
| UI-26 | Plan card (Later) | NOT BUILT | Expected |
| UI-27 | Searches panel (Later) | NOT BUILT | Expected |
| UI-28 | Viewer shown inside another page | BUILT | `?embed`, `?surface` |
| UI-29 | Phone-width layout | PARTIAL | A drag during takeover scrolls the viewer |
| UI-30 | Backend picker and bridge status (M2) | NOT BUILT | Expected |
| UI-31 | "Browser not connected" (M2) | NOT BUILT | Expected |

---

## 2. Extra things in the viewer that the spec sections do not list

**Address parameters**
- `?pace=`, `?theme=`, `?embed`, `?session=` (`main.tsx:30,48,56,61`).
- A missing token shows "refused" rather than a demo.

**Token and connection handling**
- Token taken from the `#` fragment, kept in `sessionStorage`, removed from the address; reload on `hashchange` (`connection/address.ts`, `main.tsx:40-44`). This belongs to §4.10, which I did not audit.
- Close code 4404 treated as refused (`socket:36`).
- Retry delays of 0.5, 1, 2, 5 s.
- Old pictures released after 1 s.
- Held keys released when the picture loses focus (`BrowserPane:169-172`).

**Recordings beyond the §9.3 states**
- `empty`, `person_unasked`, `dialog`, `denied`, `own_browser` (`demo/sessions.ts:150-179`).

**Buttons and controls**
- "Keep running", "Dismiss", "Copy as text".
- Icon buttons for full and split view (`App:291-297`, `StatusPanel:136-140`).
- A filled blue "person" button and a filled red confirm button.

**Wording the spec does not give**
- Help kinds ("Sign-in needed" and three more) and the help hint.
- Dialog kinds and "The agent is answering it."
- Outcome toasts, "Saved <file> (<size>)", "Browsing data cleared.", "Copied."
- "Press Ctrl+Alt+Enter to leave the browser".
- Placeholders "Nothing to show yet" and "Connecting…".
- Five refusal reasons for settings and "The settings could not be loaded."

**Display details**
- Lock or globe icon in the address pill.
- Tool name, "Returned to the agent" and address in the drawer.
- "Returned to the agent" in the summary.

**Tokens not in §9.5**
- `--scrim`, `--frame-dim`, `--tracking-caps`, `--tracking-title`, `--duration-live`.
- 19 layout tokens (`tokens.css:101-119`).
- The concrete `--shadow-float` values.

**Settings controls**
- Types `path` and `action`; per-choice `disabled`.

**Other**
- 31 icons, several unused (status M15).
- `favicon.svg`.

---

## 3. The ten most important gaps

1. **No real settings.** There is no settings API in the service and no client for one. A live session offers two settings, in memory. Twenty exist only in `demo/settings.ts`, where three are on the wrong surfaces and "Clear data" reports success while doing nothing.
2. **An unknown event breaks the viewer (from reading).** Add a default case in `reducer.ts`, or filter in `socket.ts`, before any milestone 2 event such as `bridge_changed` is sent.
3. **No off switch for P, T, A, F.** This fails WCAG 2.1.4 (level A), under a stated target of 2.2 AA.
4. **Takeover input is incomplete.**
   - Tab is never sent to the page.
   - Focus is not moved to the picture on takeover.
   - A drag on a phone scrolls the viewer (no `touch-action`, capture or `pointercancel`).
   - Phone typing is not built.
5. **Hand-back and the controls are optimistic.** The "Handed back" toast shows before the service confirms. There is no "handing back", "failed", "working" or "disabled" state, and a command sent while disconnected is dropped silently.
6. **No session picker.** The session can only be chosen with `?session=`.
7. **The viewer does not get its `viewer.*` options from the service.** Stale-after, idle divider, release chord and toast time are constants.
8. **Focus is lost after several buttons (from reading).** Pause, Resume, Take over, Hand back, Done, Couldn't do it, and cancelling the clear-data question remove the focused button without moving focus.
9. **Card and notice states are thin.**
   - Dialog card: no outcome, no time left.
   - Approval and help outcomes are toasts only.
   - No "limit reached" notice.
   - The lost-connection notice has no next action.
   - No address "loading".
   - No target "acted".
   - The step drawer has no raw result, and the approval card has no "why" or site.
10. **Smaller rule breaks.**
    - Red is used for Deny, Clear data and refusals, against the "red only means blocked, failed, stop" rule.
    - Seven interface strings plus the unit text sit outside `wording.ts`, and nine `W` keys are unused.
    - Opacity, `color-mix` and `line-height` values escape the token test.
    - Toast timing is wrong when two overlap.
    - `?demo` cannot be stepped by hand.
    - An unknown `?state=` name plays the signup run without saying so.

---

## 4. Counts per verdict

| Section | BUILT | PARTIAL | NOT BUILT | DIFFERS | Rows |
|---|---|---|---|---|---|
| 9.1 Principles | 5 | 3 | 0 | 0 | 8 |
| 9.2 Layout | 9 | 2 | 0 | 1 | 12 |
| 9.3 States | 11 | 0 | 1 | 0 | 12 |
| 9.4 Components | 10 | 12 | 2 | 1 | 25 |
| 9.5 Tokens | 32 | 2 | 0 | 1 | 35 |
| 9.6 Wording | 20 | 3 | 3 | 0 | 26 |
| 9.7 Timeline rows | 14 | 1 | 1 | 0 | 16 |
| 9.8 Keyboard | 8 | 1 | 0 | 1 | 10 |
| 9.9 Accessibility | 7 | 2 | 1 | 0 | 10 |
| 9.10 Motion | 4 | 0 | 0 | 0 | 4 |
| 9.11 Build | 9 | 0 | 1 | 0 | 10 |
| 9.12 Settings | 12 | 19 | 1 | 4 | 36 |
| 9.13 Later | 0 | 0 | 6 | 0 | 6 |
| 4.8 Protocol (client) | 39 | 3 | 1 | 0 | 43 |
| 15.19 Feature rows | 13 | 9 | 9 | 0 | 31 |
| **Total** | **193** | **57** | **26** | **8** | **284** |

- Of the 26 NOT BUILT rows, 20 are marked milestone 2, milestone 4, Next or Later in the spec.
- The six that are milestone 1 scope: the session picker (counted twice, in 9.4 and as UI-03), the Browser picker component row (itself labelled M2 in 9.4), the 2.1.4 switch, stepping a demo by hand, and... see note below.
- Note: the milestone-1 NOT BUILT rows are exactly four distinct things — session picker (9.4 and UI-03), 2.1.4 off switch (9.9), demo stepped by hand (9.11) — plus two rows whose features are later-milestone but sit in M1-era tables (Browser picker in 9.4, `bridge_changed` in 4.8). The status page's seven missing sub-states are folded into PARTIAL component rows, not counted separately.
- The §15.19 rows overlap the §9 rows, so the total counts some features twice.
