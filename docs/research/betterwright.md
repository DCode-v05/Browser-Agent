# BetterWright — research notes for the Python browser-use engine spec

Researched 2026-10-03 by reading the source. Nothing was installed or run.

- Repo: https://github.com/BetterWright/betterwright
- Clone: `<scratch>/research/bw/` (all `path:line` references below are relative to that folder)
- Commit: `ec55a321a6358adf9ad3bfeade01fb735590b8bc` — "deps: bump fast-uri from 3.1.6 to 3.1.7 … (#229)", committed 2026-09-29T19:54:22-04:00
- Package version at that commit: 2.8.8 (`package.json:3`)

How the clone was made: `git clone --depth 1` failed because the scratch path is 208 characters and pack file names pushed past Windows' 260-character limit. I used `git init` + `core.longpaths=true` + `git fetch --depth 1 origin HEAD`, renamed the pack files Git had left under mangled temp names, and wrote `.git/shallow` by hand. The working tree is a normal checkout of the commit above (468 tracked files, `git status` clean). No fallback to the web UI was needed.

Evidence levels used below:
- **code** — I read the implementation at the cited lines.
- **docs** — stated in the repo's own docs; I did not read the implementing code. Treat as the authors' claim.
- **UNVERIFIED** — I could not confirm it either way.

---

## 1. Repository facts

| Fact | Value | Source |
| --- | --- | --- |
| License | MIT; Ghostery ad-blocker dependency is MPL-2.0 | `LICENSE`, `NOTICE.md:26-30` |
| Language / runtime | TypeScript 7, ESM. CLI needs Bun >= 1.4; the library also imports from Node 22+ | `package.json:119-122`, `README.md:20-22` |
| Runtime deps | `playwright-core` 1.61.1, `@ghostery/adblocker-playwright` 2.18.2, `tldts` 7.4.9 | `package.json:131-135` |
| Optional deps | `patchright-core` 1.61.1 (stealth driver), `rookie-cookies` 0.6.0 (cookie reader), `ws` 8.21.0 (Electron) | `package.json:183-187` |
| Optional peers | `@modelcontextprotocol/sdk` >= 1.13, `@anthropic-ai/sdk` >= 0.30, `electron` >= 43.4.1 | `package.json:136-149` |
| Stars / forks | 324 / 23 (GitHub API, fetched 2026-10-03) | api.github.com |
| Created / last push | 2026-07-13 / 2026-09-29 | api.github.com |
| Release cadence | 57 versions in `CHANGELOG.md` from 1.1.3 (2026-07-24) to 2.8.8 (2026-09-21): roughly one release per day, several days with 3-5 releases | `CHANGELOG.md` headings |
| Contributors | CuriosityOS 242 commits, SSHdotCodes 82, `cursoragent` 18, then single digits. Many branches are named `agent/*` and `capy/*` | GitHub API, `git ls-remote` |

Reading: a ~11-week-old project with very high churn and heavy AI-assisted authorship. Expect API instability; treat it as a source of ideas, not a dependency.

## 2. Code map

| Area | Files | Lines |
| --- | --- | --- |
| `src/` | 111 | 47,502 |
| `bin/` | 2 | 2,488 |
| `types/` (hand-written .d.ts) | 22 | 2,518 |
| `tests/` | 135 | 46,225 |
| `docs/` | 38 | 6,932 |
| `benchmarks/` | 58 (6,837 lines of harness code, 1,950 lines of reports) | |
| `patches/` | 8 (Chromium + V8 patch sets for 150, 151, 153) | |
| `scripts/chromium/` | build/package scripts for the fork | |
| `skills/` | 7 skill packs | 404 |

Largest modules (lines): `worker.ts` 2,847 · `agent.ts` 2,650 · `vault.ts` 2,570 · `bin/cli-main.ts` 2,426 · `client.ts` 1,970 · `live-view.ts` 1,642 · `captcha-runtime.ts` 1,444 · `credential-fill.ts` 1,403 · `live-view-html.ts` 1,333 · `daemon.ts` 1,248 · `guard-proxy.ts` 1,190 · `captcha-solver.ts` 1,134 · `browser-providers.ts` 1,129 · `worker-realm.ts` 1,048 · `local-ai-catalog.ts` 1,033 · `mcp-server.ts` 734 · `snapshot.ts` 632 · `ui-batch.ts` 522.

### Process model (three layers)

```
CLI process ──unix socket / named pipe──▶ session daemon ──stdio JSON lines──▶ worker ──CDP pipe──▶ BetterChromium
 (thin)                                   (owns BetterWright client,          (Playwright, node:vm sandbox,
                                           policy, vault, agent loop)          SOCKS guard proxy, live view)
```

The MCP server and the SDK skip the daemon: they hold the client in-process (`src/mcp-server.ts:702`).

### Call flow, CLI `run`

1. `bin/cli-main.ts:2222` `runCli` → `cmdRun` (`:640`) reads the snippet from `-c`, a file or stdin (`:536-541`).
2. `acquireRunBrowser` (`:595`) → `connectSessionDaemon` (`src/daemon-client.ts:253`). If no daemon answers, it spawns `betterwright __daemon` detached, config on stdin, never argv (`:170-208`), and polls the socket for up to 8 s (`:33, :223`).
3. Handshake compares package version and a config signature (`:291-301`). A mismatched idle daemon is shut down and replaced; a mismatched busy one is left alone and the call falls back to a one-shot in-process browser with a warning (`:303-325`, `bin/cli-main.ts:619-626`).
4. Daemon calls `BetterWright.run` (`src/client.ts:1239`) → per-session FIFO lane (`:600-606`) → `_dispatch` (`:1808`) writes one JSON line to the worker's stdin.
5. Worker `execute` (`src/worker.ts:2394`): `ensureBrowser` (`:1174`) → `buildSandbox` (`src/worker-sandbox.ts:463`) → `compileCode` (`src/compile-code.ts:54`) → `script.runInContext` (`src/worker.ts:2468`) → summarize, challenge scan, automatic UI directory, spill check → `buildEnvelope` (`:1772`) → `sendResult` (`:518`).
6. While the snippet runs, the worker makes `rpc_request` callbacks to the client (`guard`, `vault`, `host_connect`, capture) which are answered on a separate reader so a navigation cannot deadlock on its own authorization (`docs/architecture.md:37-49`, `src/client.ts:991-1059`).
7. CLI prints the envelope as JSON — compact when piped, indented on a TTY — and exits 0 on `ok:true`, 1 otherwise (`bin/cli-main.ts:658-660`).

### Call flow, MCP

`betterwright mcp` → `runMcpServer` (`src/mcp-server.ts:673`) builds one `BetterWright` from env vars (`:681-702`) and registers `listTools`/`callTool` (`:709-711`). Every tool except `browser_doctor` and `browser_handoff` ends in `browser.run(code, …)` or `browser.fillCredential(…)`; `browser_batch` and `browser_record` are compiled into snippets server-side (`:547-550`, `:619-624`).

---

## 3. Observation format ("compact observations")

There are three distinct things; the README's phrase covers all of them.

### 3.1 The accessibility snapshot — code

`snapshot(options)` calls Playwright's `locator.ariaSnapshot({mode: "ai"})` on `body`, a CSS selector, or `aria-ref=<ref>` (`src/worker-snapshots.ts:68-79`), then post-processes the YAML text:

1. **Password scrub** — reads every `input[type=password]` value in every frame, registers each with the redaction set, and replaces it with `[redacted]` in the text (`:28-59`). This was added after their own benchmark caught a leak (`benchmarks/browser-agent-headtohead/REPORT.md:51-60`).
2. **Compression** `compressSnapshot` (`src/snapshot.ts:407-413`, rules in `:268-379`):
   - drop `- /url:` property lines unless `{urls:true}` (`:272`)
   - cap accessible names at 100 chars (`:168, :237-247`)
   - drop `[cursor=pointer]` on inherently interactive roles (`:149-167, :282-283`)
   - strip `[ref=…]` from `generic|paragraph|heading|text|img` unless the node carries a state/interaction marker (`:145-146, :284-288`)
   - drop nameless images (`:291-298`)
   - hoist children of bare `generic` wrappers (`:301-304`)
   - turn text-only paragraphs/generics into `text` lines and merge adjacent text (`:307-346`)
   - inline a sole text child; drop a value equal to the name; collapse 2-3 text children of a ref'd container into one line (`:351-378`)
   - lines that do not match the grammar pass through untouched (`:205, :382-383`)
3. **Interactive filter** `filterInteractive` when `{interactive:true}` (`src/snapshot.ts:29-90`): keep lines whose role is button/link/textbox/searchbox/combobox/checkbox/radio/switch/slider/spinbutton/menuitem*/option/tab/treeitem/listbox/iframe or that carry `[cursor=pointer]` (`:8-12`), their ancestors, `status`/`alert` subtrees, column headers of kept tables, and short (<= 300 chars) text/cell lines under kept list items and rows (`:76-87`). Empty result → the literal `(no interactive elements)` (`:89`).
4. **Header line** `page <pageId> <url> "<title <=120 chars>"` (`src/worker-snapshots.ts:96-106`).

Real example from the tests (`tests/node/snapshot.test.ts:11-22`, input as Playwright emits it):

```
- generic [active] [ref=e1]:
  - navigation [ref=e2]:
    - link "Home" [ref=e3] [cursor=pointer]:
      - /url: "#a"
  - main [ref=e5]:
    - heading "Title" [level=1] [ref=e6]
    - paragraph [ref=e7]: Static text.
    - generic [ref=e8]:
      - textbox "Email" [ref=e9]
      - button "Submit" [ref=e10]
```

Guaranteed transforms (same file):
- `- link "Docs" [ref=e2] [cursor=pointer]:` + `  - /url: /docs` → `- link "Docs" [ref=e2]` (`:169-179`)
- three nested bare generics around a button → `- button "Go" [ref=e3]` (`:222-230`)
- an article with two paragraphs and a text → `- article [ref=e1]: First sentence. Second sentence. Trailing note` (`:262-273`)
- `- button "Submit" [ref=e2]: Submit` → `- button "Submit" [ref=e2]` (`:321-324`)

What the model receives (`docs/browser-api.md:100`): `"page page-1 https://… \"Sign in\"\n- button \"Sign in\" [ref=e12]…"`.

Authors' claim: compression "typically halves the size of a real page's tree" (`docs/browser-api.md:118-124`). No measurement of that ratio is in the repo — UNVERIFIED.

### 3.2 Refs / handles — code + docs

- Refs are Playwright's own `[ref=eN]` markers; frame-qualified as `f1e2`, nested `f2e2` (`src/worker-snapshots.ts:64`, `tests/node/snapshot.test.ts:117-158`).
- Act with `page.locator('aria-ref=e12')`; scope a later snapshot with `{ref:'e31'}` (`docs/browser-api.md:95-112, :130`).
- Refs are reassigned on every snapshot and go stale on re-render; the prompt forbids guessing them (`docs/browser-api.md:110-112`).
- Page handles: `page-N` ids from a counter (`src/worker.ts:811-818`); `usePage`/`closePage` accept id, index or page object.

### 3.3 Size caps — code

| Cap | Value | Source |
| --- | --- | --- |
| Snapshot `maxChars` default / ceiling / floor | 10,000 / 20,000 / 1,000 | `src/worker-snapshots.ts:9-10, :118-121` |
| Over-limit behaviour | **refuses** with the actual size and scoping hints; never truncates | `:126-141` |
| Snippet result (`outputLimit`) | 12,000 chars; larger results are spilled to a file and replaced with `{truncated, preview, fullOutputPath}`; preview = first 75% + last 15% of the limit | `src/worker.ts:106, :2535-2567` |
| Result envelope | 28,000 chars; on overflow console/events/pages/artifacts/warnings are trimmed, then dropped, and `envelopeTruncated:true` is set | `:98, :518-531` |
| Result summarisation | arrays/maps/objects limited to the first 200 entries, depth 8 → `"[Max depth]"`; no truncation marker | docs — `docs/browser-api.md:24-27` |
| Console messages per call | 20, each 300 chars | `src/worker-sandbox.ts:23-24` |
| Events per session | 40, each 4,000 chars | `src/worker.ts:93, :795-809` |
| Automatic UI directory | 2,400 JSON chars | `src/automatic-ui.ts:4` |
| Failure evidence | 4 excerpts x 300 chars, 200 ms budget | `src/worker.ts:2626-2630` |
| Annotated screenshot boxes | 150 | `src/snapshot.ts:427` |
| Agent observation | 12,000 chars | `src/agent.ts:68` |

The spilled file is wrapped in `<untrusted_tool_result source="betterwright">` with a warning never to follow instructions inside it (`src/worker.ts:2542-2559`).

### 3.4 Diffing — code

`snapshot({diff:true})` keeps the last delivered snapshot per page, keyed by `[ref, selector, interactive, depth, urls]` so only like is compared with like (`src/worker-snapshots.ts:21, :88-94`). Output is `diff vs previous snapshot (+A -R)` followed by `+`/`-` lines only, or `(no changes since previous snapshot)` (`:111-117`). The algorithm trims common prefix/suffix, short-circuits one-sided and no-shared-line changes, then runs an LCS with interned line ids and checkpointed rows; both sides are capped at 3,000 lines, beyond which the full snapshot is returned (`src/snapshot.ts:458-632`). A refused (over-limit) snapshot does not become the baseline (`src/worker-snapshots.ts:122-125`).

### 3.5 The automatic UI directory (`result.ui`) — code

After the first navigation to an origin+pathname, if the site has no WebAgents manifest and the caller did not pass `automaticUI:false`, the worker attaches a `betterwright-ui/1` directory (`src/worker.ts:2519-2522`): `{protocol, tool:"browser_batch", controls:[{target, actions, options?}], evidence:[{kind,text}], truncated, hint}`. `compactAutomaticUI` fits it into 2,400 chars by keeping up to two evidence entries, putting action buttons first, dropping select option lists, then dropping whole controls — it never shortens a target string because a shortened label is not a valid handle (`src/automatic-ui.ts:17-54`, guaranteed by `tests/node/automatic-ui.test.ts:19-53`). It is suppressed when the snippet already returned a directory (`:8-13`).

On a snippet failure the envelope may carry `ui.evidence` only (`src/worker.ts:2625-2635`).

### 3.6 Text versus screenshot ("visual proof") — code + docs

There is **no automatic chooser**. The decision is pushed to the model through the prompt as an escalation ladder (`src/prompt.ts:21-23`, `docs/browser-api.md:183-188`): known locators / UI directory → `snapshot({interactive:true})` → full `snapshot()` → `snapshot({diff:true})` → `screenshot({annotate:true})` "only for layout/pixels".

Screenshots are artifacts with an intent tag (`src/worker-sandbox.ts:414-461`):
- `kind: "proof" | "question" | "debug"` (plus `captcha`, set by the runtime); returns `{kind, path, media: "MEDIA:<abs path>", annotations?}`.
- `question` sets `session.awaitingAnswerSince`, which holds the pages open for up to 24 h (`:458`, `src/worker.ts:99`).
- `annotate:true` draws ref-labelled boxes over interactive elements (including iframes), captures, removes the overlay (`:428-450`).
- "Proof" is a prompt-level convention: capture one in the same call as the final verification, inspect it, retake if blank/clipped (`src/prompt.ts:41`, `src/agent.ts:219`). The harness returns the last proof path as `result.proof` (`docs/agent.md:46-63`).
- Images reach the model as native image content in MCP (`src/mcp-server.ts:234-237`); the built-in agent attaches image bytes only to the latest tool turn (`src/agent.ts:420-442`).

---

## 4. MCP surface — code (`src/mcp-server.ts`)

Transport: stdio only (`:713`). Server `instructions` = `BROWSER_TOOL_GUIDANCE` (`:706`, text in `src/tool-guidance.ts:2`). One browser for the server's lifetime (`:678-702`). Per-snippet timeout 120 s, env-overridable, min 5 (`:122-138`).

| Tool | Parameters | Notes |
| --- | --- | --- |
| `browser` | `code` (string, required), `session` (string, default `"default"`), `note` (string, default `""`) | Schema `src/tool-schemas.ts:106-117`. Description at `:240-243` lists the globals and the plan-then-batch / challenge rules. Cannot download. |
| `browser_batch` | `url`, `discover` (bool), `query` (<=32 strings <=500 chars), `operations` (1-32 of `{id, action, target, value, irreversible}`), `allowWrites`, `allowIrreversible`, `allowPasswords`, `observe`, `minIntervalMs` (0-1000), `proof`, `session`, `note`; `additionalProperties:false` | `:247-297`. `action` enum: `fill, click, select, check, uncheck, press, read, readUrl`. |
| `browser_download` | same as `browser` | Sets `approvedDownloads:true` server-side; refused when policy is `deny` (`:642-649`). The model can never pass the approval itself (`:633-637`; test `protocol-mcp-download-deny`). |
| `browser_record` | `action` (start/stop/status/restart, required), `session`, `name`, `fps` 1-60 (60), `maxWidth` (1280), `maxHeight` (720), `quality` 1-100 (80), `maxDurationMs` (300,000; max 3,600,000) | `:366-380`. Options only with start/restart (`:543-546`). |
| `browser_login` | `id`, `username`, `generate`, `length` (24), `includeSymbols`, `label`, `matchMode`, `usernameSelector`, `passwordSelector`, `currentPasswordSelector`, `confirmPasswordSelector`, `submitSelector`, `submit` (default false), `session` | Only listed when a vault exists (`:414-420`). Schema `src/tool-schemas.ts:55-89, :119-125`. Calls `browser.fillCredential` (`:523-529`). |
| `browser_handoff` | `action` (start/status/stop, default start), `reason`, `session`, `interactive` (default true) | `:344-364`, handler `:457-512`. |
| `browser_doctor` | none | Returns `doctorReport()` JSON (`:518-522`). |

Result shape for run-type tools (`contentForResult`, `:196-238`): one text block containing compact JSON with only non-empty fields — `ok`, `result`, `error`, `pendingCredential`, `console`, `files` (non-image artifacts), `pages`, `challenges`, `skills`, `warnings`, `webagents`, `ui`, `duration_ms` — followed by image content blocks for screenshots. Tool-level errors return `{content:[{type:"text", text}], isError:true}` (`:660-665`). If a live view is active, human chat typed in the viewer is appended as an extra text block marked as fresh user instructions (`:450-456`).

### What "UI batches" are — code (`src/ui-batch.ts`)

A UI batch is one guarded, ordered transaction of semantic UI operations executed inside the worker, so the model spends one tool call instead of one per click.

- Up to 32 operations; each has a unique `id` matching `^[A-Za-z][A-Za-z0-9_-]{0,63}$`, an action, a target and a value (`:6-24, :382-404`).
- Target uses exactly one of `ref | role | label | text | placeholder | testId | css`, refined by `name`, `exact`, `nth`, and `frameName` or `frameUrlIncludes` (`:68-148`). Mapped to `aria-ref=`, `getByRole`, `getByLabel`, `getByText`, `getByPlaceholder`, `getByTestId`, `locator`.
- **Ambiguity fails closed**: after waiting for attachment, the locator must match exactly one element (`:150-163`).
- **Writes are opt-in**: any non-read action needs `allowWrites:true`; `irreversible:true` operations need `allowIrreversible:true` (`:391-396`).
- **Passwords**: `fill` on `input[type=password]` is rejected unless `allowPasswordFill` (`:257-265`).
- **Mandatory verification**: a batch with writes must end in `read`/`readUrl` with a non-empty expected substring, or set `observe:true` (`:405-417`). The read polls every 25 ms for up to 10 s (`:198-224`); `readUrl` likewise (`:226-241`).
- **Stale-success guard**: if the expected text was already visible before the batch, the read first waits for tracked `document|fetch|xhr` activity to settle (max 2.5 s) (`:243-255, :355-369, :450-458`).
- All values are validated before the first write (`:267-286`). Stop on first error; the error lists completed ids and says earlier writes are not rolled back (`:494-497`).
- Result: `{protocol:"ui-batch/1", pageUpdated, durationMs, results:{id:{…}}, verification?:"observed", ui?}` (`:508-516`).

MCP `browser_batch` has three modes (`src/mcp-server.ts:556-629`): `{url}` navigates and returns the URL (the automatic directory rides on the envelope), `{url|discover, query}` returns `controls.directory()`, `{operations}` runs the batch and, with `proof:true`, appends a proof screenshot.

Related, same idea for cooperating sites (docs + `src/worker-sandbox.ts:329-412`): `webagents.discover()/batch()` posts a dependency graph of up to 32 operations to an endpoint the site publishes in `/webagents.md`; `webmcp.tools()/invoke()` calls tools a page registers through Chromium's WebMCP API. Both label results `trust: "untrusted_external_data"`.

---

## 5. Code mode (`run` snippets)

### Execution — code

- The snippet is compiled twice at most: as an expression `(async () => (CODE\n))()` or as statements `(async () => {\nCODE\n})()`. A regex on the leading token picks which to try first; the other form is tried on `SyntaxError`, and the statement-form error is the one surfaced (`src/compile-code.ts:38-76`). Effect: a single trailing expression returns automatically, a multi-statement block needs `return`.
- It runs in a fresh `vm.createContext(Object.create(null), {codeGeneration: {strings:false, wasm:false}})` built per execution (`src/worker-sandbox.ts:468-472`).
- Timeouts: the synchronous part of the script is limited to 1,000 ms by `runInContext({timeout})` (`src/worker.ts:121, :2468-2470`); the whole call is raced against a timer, default 30,000 ms, floor 1,000 ms (`:2471-2501`). JS API default 30 s, min 5 (`src/client.ts:62, :567`); MCP default 120 s. Playwright action timeout 5 s, navigation 30 s (`src/worker.ts:113-114`).
- A timeout raises `BW_TIMEOUT`, sets `restartWorker`, and the worker process exits after replying (`:2605-2607, :2669-2672`). The client has a second watchdog at timeout + 5 s that kills and restarts the worker (`src/client.ts:1844-1853`). The client object stays usable; tabs and in-memory `state` are lost, the on-disk profile survives (`docs/sdk.md:138-152`).
- Credential promises started by the snippet are joined before the result is accepted (`src/worker.ts:2478-2489`).

### Globals the snippet sees — code (`src/worker-sandbox.ts:502-637`)

`page` (getter for the session's current page), `pages`, `context` (wrapped), `state` (plain object persisted per session), `console` (captured), `URL`, `URLSearchParams` (re-implemented inside the realm), `openPage`, `usePage`, `closePage`, `snapshot`, `screenshot`, `artifactPath`, `recording.{start,stop,status,restart}`, `dialogs.{acceptNext,dismissNext}`, `captcha.*`, `human.{click,type,scroll}`, `overlays.dismiss`, `controls.{inspect,directory,batch}`, `media.inspect`, `site.{requests,assets,read,request}`, `webmcp.{tools,invoke}`, `webagents.{discover,batch}`, `credentials.*`. All helper namespaces are frozen. No `process`, `require`, `import`, `fs`.

### Sandbox facade — code (`src/worker-realm.ts`)

Playwright objects are wrapped in proxies. Removed everywhere: any property starting with `_`, `addListener, browser, constructor, context, exposeBinding, exposeFunction, newCDPSession, off, on, once, prependListener, removeAllListeners, removeListener, request, route, routeFromHAR, routeWebSocket, screenshot, serviceWorkers, unroute, unrouteAll` (`:70-92, :134-140`). Extra per type: `BrowserContext` loses `addCookies, clearCookies, close, cookies, newPage, pages, setStorageState, storageState, tracing` (`:142-156`); `Download` loses `createReadStream, path, saveAs`; `Request`/`Response` lose the full-header methods (`:157-181`); `headers()` has `cookie`/`set-cookie` filtered out (`:184-191`). `page.on/once/off` is re-added for `console` and `pageerror` only. File inputs must resolve inside the artifact directory; writes must be under it (`:201-226`).

The authors are explicit that this is **defense in depth, not a boundary**: "We do not claim `node:vm` is a security boundary — it isn't" (`docs/architecture.md:78-81`).

### Result envelope — code + docs

Worker envelope (`src/worker.ts:1805-1826`), documented at `docs/javascript.md:131-154`:

`ok`, `result`, `error`, `errorCode` (e.g. `BW_ABORTED`), `effectMayHaveCommitted`, `console`, `events`, `artifacts` `[{kind, path, media, size?}]`, `pages`, `challenges`, `warnings`, `webagents`, `ui`, `skills`, `profileMode` (`persistent`|`ephemeral`), `pendingCredential`, `envelopeTruncated`, `durationMs`. Empty diagnostic arrays are deleted before sending (`src/worker.ts:532-536`). The CLI adds `session`.

Everything is passed through `redactDeep` before it leaves the worker (`:1808-1824`). Failures inside the browser are values (`{ok:false, error}`), not exceptions; the client throws only when it cannot start (`docs/sdk.md:114-136`).

Cancellation: `run(code, {signal})`. Aborting dispatched work stops the whole worker and returns `errorCode: "BW_ABORTED", effectMayHaveCommitted: true` (`src/client.ts:1809-1833`).

---

## 6. Session persistence

### Daemon — code (`src/daemon.ts`, `src/daemon-client.ts`)

- One daemon per `(BETTERWRIGHT_HOME, profile)` (`src/daemon.ts:3-10`). Socket `<home>/daemon.sock` or `daemon-<name>.sock`, mode 0600 inside a 0700 home; a named pipe on Windows; a short hashed path in the temp dir when the unix path would exceed ~100 bytes (`:118-126`, `docs/sessions.md:109-127`).
- Protocol: newline-delimited JSON, ops `hello, call, exec, attach, interrupt, close_session, status, shutdown` (`:12-47`). `call` only reaches whitelisted client methods.
- Auth is filesystem permissions only; "Sessions are collaboration scopes, not a security boundary" (`:49-51`).
- Lifecycle constants (`:81-104`): session idle TTL 15 min (`BETTERWRIGHT_SESSION_TTL_SECONDS`, floor 30 s), reaper every 15 s, daemon exits 60 s after the last session closes, orphaned agent run interrupted after 30 s (`BETTERWRIGHT_ORPHAN_GRACE_SECONDS`, 0 disables), replay buffer 512 frames, finished run kept 60 s, request line max 8 MiB, shutdown deadline 10 s.
- `exec` runs the agent loop **inside the daemon**, so a dropped CLI connection re-attaches with a cursor and replays missed frames (`:20-41`, `src/daemon-client.ts:45-46, :478`).
- Daemon stderr → `<home>/daemon.log`, rotated at 4 MiB (`src/daemon-client.ts:42, :161-168`).

### State between calls — code

- A **session** = `{pages, currentId, state, events, artifacts, cursor, captchaTargets, …}` (`src/worker-session.ts:7-31`), max 32 pages (`:3`). Popups are adopted automatically (docs).
- Sessions share one browser context and therefore one cookie jar; a **profile** is a different user-data-dir, lock, daemon and transcript store (`docs/sessions.md:47-75`).
- Calls within a session are strictly ordered; different sessions run concurrently (`src/client.ts:600-606`).
- `exec` transcripts are saved to `<home>/sessions/<name>/transcript.json` with stale browser observations replaced by a one-line stub, keeping only the 2 most recent and anything under 600 chars, capped at 150,000 chars (`src/session-store.ts:1-36`).
- **Page parking**: 750 ms after the last execution on a headless session unwinds, its pages are frozen via the native page lifecycle and woken before the next call; headed, live-viewed and recording pages are never parked (`src/worker.ts:209-227`, `src/page-park.ts:1-36`). Motivation given: five idle tabs burned ~110% CPU (`src/page-park.ts:9-10`).

### Profiles, cleanup, crash recovery — code

- Profile dir `<home>/browser/profile` or `browser/profiles/<name>` (`src/client.ts:619-633`). Launched with `chromium.launchPersistentContext` (`src/worker.ts:1493-1504`).
- Advisory lock = sibling directory `<profile>.betterwright-lock/owner.json` with a 15 s heartbeat and 60 s staleness, so a hard-killed owner's lock expires even when the PID is reused (`src/profile-lock.ts:1-20`).
- A second worker on the same profile gets an **ephemeral** profile under `browser/runtime` (signed out) plus a warning; it is deleted on release (`src/worker.ts:591-604, :1238-1250`). The envelope reports `profileMode`.
- A profile upgraded by a newer Chromium is refused rather than opened (`src/browser-runtime.ts:30-47`).
- Worker shutdown has a 15 s failsafe (`src/worker.ts:119`). Worker start handshake timeout 15 s (`src/client.ts:63`).
- Artifacts quota 100 MiB per session, downloads 50 MiB, page idle timeout 1,800 s (`src/client.ts:660-662`).
- Live view survives a worker restart on the same port and token (`src/client.ts:611-615, :1906-1909`).

---

## 7. Network policy

### What is enforced where — code

| Layer | Mechanism | Applies to |
| --- | --- | --- |
| A. Request routing | `context.route("**/*")` asks the policy for every HTTP request; denial or any error → `route.abort("blockedbyclient")` | all browsers incl. remote CDP "where the provider supports it" — `src/worker.ts:1097-1157` |
| B. Transport proxy | Chromium is launched with `--proxy-server=socks5://127.0.0.1:<port>` and `--proxy-bypass-list=<-loopback>`; the worker's SOCKS5 proxy authorizes the hostname, resolves it itself, authorizes **every** resolved IP, then dials one of those literals | locally launched browsers and Electron host targets only — `src/chromium-args.ts:212-221`, `src/guard-proxy.ts:627-690` |
| C. Chromium flags | `--webrtc-ip-handling-policy=disable_non_proxied_udp` so WebRTC cannot send UDP around the TCP proxy | managed fork — `src/browser-runtime.ts:107-115` |

Notes:
- They deliberately do **not** use Playwright's `proxy` option, because for SOCKS it injects `--host-resolver-rules` which paints an infobar (`src/worker.ts:1442-1446`). Caller-supplied proxy, debugging-port, user-data-dir, `--lang`, `--headless` and `--fingerprint*` switches are rejected outright (`src/chromium-args.ts:38-79`).
- They deliberately do **not** install Playwright WebSocket interception "because it changes the browser's WebSocket path observably enough for commercial bot defenses"; WebSockets are covered by layer B only (`src/worker.ts:1159-1163`).
- The policy itself lives in the **client** process; the worker asks over RPC (`src/client.ts:1027-1032`). Only a stock `NetworkPolicy` with no custom hook is marked `cacheable`, and then only host-scoped (non-navigation, non-document, non-download, non-WebSocket) decisions are cached, 5 s TTL, 2,048 entries; a non-cacheable answer flushes the cache (`src/guard-url.ts:41-42, :100-136`).

### Policy rules — code (`src/policy.ts`)

Order in `check` (`:226-261`) / `checkHost` (`:263-304`): scheme (only http/https/ws/wss, plus `about:blank`, `data:`, `blob:`) → metadata floor → `blockHosts` → `allowHosts` → IP category → `localhost`/`*.localhost` → single-label, `.local`, `.internal`, `.lan` names → custom hook (re-checked against the metadata floor).

- **Defaults are permissive**: `allowPrivateNetwork` and `allowLoopback` both default to true (`:206-207`). `--block-private-network` / `--block-loopback` flip them (`bin/cli-main.ts:580-585`).
- **Metadata floor** (cannot be allowlisted): hostnames `metadata.google.internal`, `metadata.goog`; addresses `169.254.169.254`, `169.254.170.2`, `100.100.100.200`, `fd00:ec2::254` and the `fd00:ec2:` prefix (`:15-25, :127-128, :251-256`).
- Private ranges include RFC 1918, 169.254/16, 100.64/10, 0/8, documentation and benchmarking ranges, multicast, reserved; IPv6 link-local fe80::/10 (compared on the first hextet, after a bug where `fe90::` slipped through — `:130-143`), site-local, unique-local, multicast; IPv4-mapped IPv6 is unwrapped first (`:49-99`).
- `allowHosts` is an exception list, not an exclusive allowlist; there is no CLI flag for "only these sites" (`docs/network-policy.md:71-74`).
- Conformance vectors: `tests/fixtures/policy-vectors.json` (714 lines).

### DNS-rebinding guard — code

`guardedTransportAddresses` (`src/guard-proxy.ts:637-690`): IP literal → used as is; RFC 6761 `*.localhost` → mapped to loopback without OS DNS; otherwise `dns.lookup(host, {all:true})`, then every address is policy-checked in parallel with `resourceType:"transport-address", resolvedFrom: host`; any denial blocks the connection; the socket is then opened to the checked literal, so Chromium never does a second lookup. Handshake timeout 15 s, connect timeout 10 s (`:17-18`). With an `upstreamProxy` (http or socks5) the guard tunnels to the validated literal through the upstream (`docs/launch-identity.md:70-80`).

### Remote-CDP limitations — docs + code

For `connectOverCDP` providers the guard proxy is not started at all (`src/worker.ts:1339-1345`). Layer A still runs; the metadata floor at transport level and the rebinding guard do not. The launch result carries a warning and `doctor` reports `warn` (`docs/browser-providers.md:220-228`). Service workers that already exist in a remote context can bypass routing (`docs/ad-blocking.md:54-60`). Remote endpoints must be `wss://`; `ws://` only for loopback (`docs/browser-providers.md:216-218`).

---

## 8. Credential vault

### Storage and encryption — code

- Files under `<home>/vault/`: `vault.key` (32 random bytes), `vault.enc`, `audit.jsonl`, `vault.lock/owner.json`; directories 0700, files 0600 (`src/vault.ts:44-46, :1380`, `docs/credentials.md:332-343`).
- `vault.enc` is one JSON line `{version:1, algorithm:"aes-256-gcm", iv, tag, ciphertext}` (base64url). The **whole record table** is one AES-256-GCM message, 12-byte random IV per rewrite, 16-byte tag, AAD `betterwright-local-credential-vault:v1` (`src/vault.ts:47-50, :448-471`). Atomic rewrite, cross-process lock.
- Limits: 4,096 records, 64 pending generated secrets, 4 MiB plaintext, 64k chars per secret (`:51-58`).
- Optional master password: the data key is wrapped with scrypt (N=131072, r=8, p=1) → AES-256-GCM, AAD `betterwright-vault-master:v1`, min 12 characters, stored as `master-key.json`, plaintext `vault.key` removed (`src/vault-key-protection.ts:4, :42-69`). Unlock lasts 15 minutes by default (docs).
- Without a master password the key file sits next to the ciphertext; the authors say this "is not a defense against malware or another process already able to read files as the same OS user" (`docs/credentials.md:366-370`).

### URL gating — code

`scopeMatches` (`src/vault.ts:247-256`): `never` → no match; an HTTPS-saved record is never offered on HTTP; `exact-origin` compares origins; `host` compares hostnames; default `base-domain` compares registrable domains via `tldts.getDomain(…, {allowPrivateDomains:true})` so `a.github.io` and `b.github.io` do not share (`:233-245`). IPs and bare `localhost` stay host-scoped. Every vault request carries the canonical current origin, computed by the worker, not by the snippet.

### Keeping values from the model — code + docs

- The worker's vault RPC surface (`handleRequest`: list, list-pending, save, update, remove, fill, generate, commit, discard) returns metadata only to snippets (`publicRecord`, `src/vault.ts:317-328`). Reveal/copy/type live on a separate owner-only API that the RPC cannot route to (`docs/credentials.md:255-312`).
- `credentials.fill` resolves the secret inside the worker and types it with trusted input; the result reports which roles were filled, not values (docs; `src/credential-fill.ts` not read line by line).
- Generated passwords are two-phase: stored as an encrypted provisional entry with an opaque `pendingId`, 60 s finalization window, excluded from list/fill until `commitGenerated` (`src/vault.ts:59`, `docs/credentials.md:53-102`). One generation per execution; if the snippet does not return the pending id the run fails with a recovery object (`src/worker.ts:2481-2487`).
- Snippets cannot overwrite an existing secret unless the host set `allowCredentialOverwrite` — the client overrides the flag on every request (`src/client.ts:1054-1059`).
- UI batches refuse password fills by default (see section 4).

### Redaction — code

- A worker-wide set of handled secrets (max 200) plus cookie values from Cookie Sync (`src/worker.ts:122-124, :311-321`). If the set fills, the worker fails closed and restarts rather than evicting plaintext while its page is alive (`:307-317`).
- `createSecretsRedactor` indexes secrets by their first 4 characters, longest-first, and replaces occurrences in strings, object keys and nested values with `[redacted]` (`src/credential-constants.ts:27-78`).
- Applied to results, console, events, artifacts, warnings, challenges, pages (`src/worker.ts:1805-1826`), spilled output (`:2550`), and error text (`:2619`).
- If a custom vault's `redact()` throws or returns a non-object, the whole envelope is withheld (`src/client.ts:1867-1885`).
- The worker deletes `DEBUG` from its environment so Playwright protocol logging cannot leak CDP payloads (`src/client.ts:693-696`).

Authors' stated limit: literal-match redaction is "defense in depth, not a confidentiality boundary"; the filled value is in the page DOM, and model-authored page code can transform it before returning it (`SECURITY.md:40-44`, `docs/credentials.md:414-427`).

### Automatic capture — docs

On by default when a vault is active (`credentialCapture`): a sensor injected into a CDP isolated world per frame captures accepted logins. Model-typed logins are saved **silently**; manual logins in a headed window get a "Save password?" banner (`docs/credentials.md:168-207`). Worth knowing before copying the vault design: it saves credentials the user never asked to be stored.

---

## 9. Human handoff (live view)

- **Trigger**: host surfaces only — agent tools `live_view`, `ask`, `handoff`; MCP `browser_handoff`; CLI `betterwright view` / `--live-view`; SDK `startLiveView()`, `waitForHandoff()`, `waitForAsk()`. Snippet code cannot start it (`docs/live-view.md:10-28`). Model guidance: use `handoff` for MFA/passkey, a CAPTCHA that resisted `captcha.solve()`, a login the vault cannot fill, a step the user should perform personally (`src/agent.ts:267`).
- **UI**: an HTTP + WebSocket server **inside the worker** serves one self-contained HTML page; frames are CDP `Page.startScreencast` JPEGs, input returns as CDP `Input.dispatchMouseEvent/KeyEvent` (`src/live-view.ts:5-6, :757, :982, :999`). Address bar, back/forward/reload, tabs, chat panel, ask chips, Done/Cancel bar (`docs/live-view.md:48-93`). Quality 60, max width 1440 (`src/client.ts:575-584`).
- **Return of control**: `waitForHandoff` resolves `{ok, action: "done"|"cancel"|"timeout", note}`; the worker resolves `timeout` just before the client timer so the worker is not restarted (`src/client.ts:1644-1680`, `src/worker-live-view.ts:172-201`). The agent is told to re-snapshot before acting. Viewer chat is drained at turn boundaries (`:266-286`); over MCP it rides on the next tool result.
- **Timeouts**: handoff and ask default 1,800 s, min 5 s (`src/client.ts:1669, :1733`). Bypasses the per-session queue so a pending handoff cannot deadlock a queued execute.
- **Security**: random 24-byte URL token required on page, HTTP and WS (`src/live-view.ts:1433`), constant-time compare (`:310-316`); optional password with a 12 h HttpOnly SameSite=Strict session cookie (`:111, :1322-1325`); login lockout 10 attempts / 15 min (docs). **Default bind is 0.0.0.0 with a LAN URL, over plain HTTP** (`docs/live-view.md:175-198`, `src/mcp-server.ts:156-159`); over MCP a non-loopback bind additionally needs `BETTERWRIGHT_LIVE_VIEW=1` (`:479-488`). Human navigation and input still pass the network policy.
- The header comment in `src/mcp-server.ts:44` still says the default host is 127.0.0.1; the code says 0.0.0.0. Stale comment.

---

## 10. CAPTCHA support — exact behaviour

**It solves, locally. It is not detect-and-hand-off, and it uses no third-party service.**

Detection (`src/challenges.ts`, `src/challenge-scan.ts`): every result is scanned in two stages (main frame always; per-frame only when something points at a challenge), covering reCAPTCHA, hCaptcha, Turnstile, Cloudflare managed checks, Google `/sorry`, Bing, plus frame-URL heuristics for DataDome, Arkose/FunCaptcha, AWS WAF, PerimeterX, GeeTest (`src/challenges.ts:289-297`, `docs/captcha.md:189-217`). A detected challenge is reported in `challenges` with `stage`, `autoSolvable`, `needsVision`, and a `captcha` screenshot artifact.

`captcha.solve(options)` (`src/captcha-runtime.ts:1123-1441`), up to 3 stages (clamped 1-3), default timeout 45 s (clamped 3-180 s) (`src/captcha-solver.ts:1124-1134`). Per-stage action table (`:1050-1114`) and implementation (`src/captcha-runtime.ts:930-1121`):

| Stage | What the code does |
| --- | --- |
| Checkbox (reCAPTCHA / hCaptcha / generic) | Finds the checkbox or widget iframe and clicks it with Bezier-curved pointer motion (`:939-998`) |
| Cloudflare Turnstile | Clicks the widget by frame-element geometry because the iframe is in a closed shadow root (`:950-958`), then waits for `cf-turnstile-response` |
| Cloudflare managed challenge | Clicks a verify control if present, then waits for clearance |
| Slider / puzzle | Drags the handle ~82-92% of an estimated track width (`:744-769`); or "drag-to-fit" by sampling the canvas for a dark piece and hole (`:894-928`) |
| Motion ("shape that grows") | Samples 3 canvas frames 420 ms apart, diffs them, clicks the grown blob, clicks Next (`:837-892, :1019-1038`) |
| Image grid | Crops the widget, overlays tile numbers, returns `status:"processing"` with the image for the **host model's vision**; `captcha.solve({tiles:[…]})` then clicks those tiles and Verify (`:658-742, :1241-1326`) |
| Text CAPTCHA | Returns a crop for the host model to read; the model types the answer itself |
| Invisible | Waits for a token |

The result envelope mimics a 2Captcha response: `status: ready|processing|error`, `requestId`, `provider`, `stage`, `cleared`, **`token`** (the provider response token when one was written into the page), `tiles`, `grid`, `artifact`, `attempts`, `local:true`, `externalApi:false` (`docs/captcha.md:41-53`, `src/captcha-solver.ts:1-12`).

Manual helpers: `captcha.detect/inspect/click/clickTiles/drag/readText` (`src/worker-sandbox.ts:113-240`).

How it is presented:
- GitHub repo description: "…and CAPTCHA solving"; `package.json` keyword `captcha`; `docs/captcha.md:5` "BetterWright solves simple CAPTCHAs inside the existing browser session".
- The default system prompt tells every model: "Use local `captcha.solve()`" and to hand off only after rejection or three distinct stages (`src/prompt.ts:37`); the MCP `browser` description says "captcha.solve() first" (`src/mcp-server.ts:243`).
- Authors' stated limits: it does not manufacture tokens offline, does not guarantee acceptance, and the live tests "do not establish that the CAPTCHA was solved" — `serverAcceptance: "unverified"` in every demo (`docs/captcha.md:227-266`). In their recorded demo runs Turnstile stayed at `processing` without a token and reCAPTCHA v2 escalated to an image grid (`docs/launch-identity.md:109-112`).
- Their own Stealth Bench runner takes the opposite stance: it "prohibits CAPTCHA solving and clicking" and counts challenges as blocked (`benchmarks/stealth-bench/README.md:37-41`).

Legal note for the spec: this is automated circumvention of a bot check by design (automated clicks, automated drags, model-vision tile selection), combined with a fingerprint-altered browser. The only disclaimer is "Use these helpers only for a legitimate flow you are authorized to complete" (`docs/captcha.md:12-16`). Detection + screenshot + human handoff can be copied without that exposure; the solver cannot.

---

## 11. Ad blocking (Ghostery)

- **Integration — code** (`src/ad-blocker.ts`, `src/worker.ts:1089-1158`): `@ghostery/adblocker-playwright` `PlaywrightBlocker.fromPrebuiltAdsAndTracking`, loaded only when enabled. The compiled engine is cached at `<home>/browser/runtime/ad-blocker-2.18.2.bin` for 7 days; refresh has a 15 s deadline; a failed refresh falls back to the cache with a warning; no cache and no network → launch error (`:14-61`).
- It is called **inside the policy route handler, after the policy allows** (`src/worker.ts:1133-1134`), so a filter exception cannot override a policy denial. They do not use Ghostery's own `enableBlockingInPage` because its `route.continue` handler would skip the guard; only the cosmetic `onFrameNavigated` hook is attached (`src/ad-blocker.ts:104-114`). Matches are aborted or fulfilled with Ghostery's redirect resources (`:85-101`). Top-level navigations are never blocked (`:77-83`).
- Side effect: new contexts are created with `serviceWorkers: "block"` when ad blocking is on (`src/worker.ts:1478, :1501`). WebSockets are not ad-filtered.
- Lists: EasyList, EasyPrivacy, Peter Lowe's, uBlock Origin filters (`docs/ad-blocking.md:32-37`). On by default; `--no-ad-block`, `adBlock:false`, `BETTERWRIGHT_AD_BLOCK=0`.
- **Measured effect**: one completed on/off pair on one ad-heavy page — CPU 11.72 s → 2.99 s (-74.5%), peak summed RSS 2,541 → 1,276 MiB (-49.8%), frames 31 → 4. Control page: +3.5% CPU, +2.8% RSS. Three of six ad-page attempts failed navigation. The authors call it "a limited observation, not a general performance guarantee" (`benchmarks/ad-blocking/README.md:5-16`, raw rows in `results.csv`).

---

## 12. BetterChromium

**What it is**: a source-patched Chromium build (currently 153.0.8010.36, release tag `betterchromium-153.0.8010.36-r2`) driven by stock `playwright-core` over the normal CDP pipe (`src/chromium-fork.ts:7, :176`, `docs/chromium-fork.md:157-162`). Patches are in the repo: `patches/chromium-153/chromium-betterchromium-153.patch` (1,364 lines, 35 files) and `v8-betterchromium-15.3.patch` (418 lines).

**It is a stealth / fingerprint-control browser.** Verified in the checked-in 153 patch (line numbers are lines of the patch file):
- `Navigator::webdriver()` returns `false` unconditionally: "Automation state is never exposed to the page" (patch 621-630).
- The `Headless` token is removed from the user agent (patch 227-232).
- UA-CH brand list reports `Google Chrome` when the `--fingerprint` switch is present (patch 212-219).
- Console/inspector reporting is deferred to a posted task and flushed on DOMContentLoaded/load "so the page-observed cost of console.* stays at the no-inspector baseline" — i.e. it defeats timing/serialization-based CDP detection (patch 682-800; the V8 patch touches `v8-console-agent-impl`, `v8-console-message`, `v8-runtime-agent-impl`).
- New switches `--fingerprint`, `--fingerprint-platform`, `--fingerprint-locale`, `--fingerprint-timezone`, `--bw-timezone` (patch 496-546).
- Deterministic **canvas and audio noise** keyed on the seed: `ImageDataBuffer::FarbleIfEnabled` (patch 1194-1245), `ApplyFingerprintAudioNoise` (patch 884, 1103).
- On software GL the WebGL debug renderer is reported as `ANGLE (Intel, Mesa Intel(R) UHD Graphics 620 …)` / vendor `Google Inc. (Intel)` (patch 940, 958).
- `ActiveText` system colour forced to system blue (patch 816-828).
- `deviceMemory` 16 and a `hardwareConcurrency` override under the macOS mask (patch 605-612, 653).

The seed is a random 5-digit number stored in the profile as `.betterwright-fingerprint-seed` and passed as `--fingerprint=<seed>` (`src/worker.ts:559-569`, `src/browser-runtime.ts:145`); `fingerprintNoise:false` withholds it.

From `docs/chromium-fork-patches.md` only:
- An optional full macOS mask (UA, UA-CH, `navigator.platform`, WebGL "Apple M4 Pro", hardwareConcurrency 12, screen geometry) behind `--fingerprint-platform=macos`; not the default — the default identity is the real host OS (`docs/chromium-fork.md:187-199`).
- Efficiency patches: Linux renderer soft limit, font-data file sharing (`:186-246`).
- **Docs/patch mismatch**: the doc (`:152-160`) says `ContentIndex`, `ContactsManager` and `NetInfoDownlinkMax` are enabled on Linux via `runtime_enabled_features.json5` and `network_information.cc`, to defeat CreepJS presence checks. Neither file nor those identifiers appear in any patch under `patches/` (grep across all four patch directories returns nothing). Either the published binary contains changes that are not in the repository, or the doc describes something that is not built. Consequence: the downloaded binary cannot be fully audited from the checked-in patches; its only integrity anchor is the pinned SHA-256.

Launch-side behaviour (code): about 20 of Playwright's behavioural default args are removed so the browser behaves like a user-launched one (`src/chromium-fork.ts:116-141, :151`); `viewport:null`; `colorScheme:"dark"`; Chromium sandbox kept on except root on Linux (`:144-161`); `--renderer-process-limit=2`; ANGLE backend forced to match real hardware so a spoofed GPU string cannot contradict the UA — the comment names PixelScan's "Masking detected" verdict (`src/browser-runtime.ts:107-146`).

Optional extra: `--stealth` / `stealthRuntimeFix` swaps the driver for `patchright-core` via a module-resolution hook so snippets execute in an isolated world and avoid `Runtime.enable` (`src/stealth-hooks.ts:1-21`, `src/client.ts:700-722`, `src/worker.ts:549-557`). Cost: snippets cannot read page main-world globals.

**Platforms**: macOS arm64, Linux x64, Windows x64 only (`src/chromium-fork.ts:163-173`). Anything else must use the provider option.

**Download and verification — code**: explicit `betterwright setup`/`update`, never an install script. Zip from `https://github.com/<repo>/releases/download/<tag>/<name>` (`src/chromium-fork-install.ts:37`), SHA-256 of the whole archive compared with constants pinned in source (`src/chromium-fork.ts:182-198`, check at `src/chromium-fork-install.ts:210-213`), staged on the destination filesystem and swapped by directory rename with rollback (`:168-171, :219, :271-282`), then a receipt `.betterwright-install.json` (version, tag, asset, sha256) is written; launch refuses a managed binary whose receipt does not match the pinned release (`src/chromium-fork.ts:302-342, :408-419`). No signature beyond the pinned hash. Windows additionally validates a side-by-side manifest and `chrome_elf.dll` (`:14-114`).

Disclaimer repeated by the authors: it "reduces common automation false positives; it cannot guarantee that a site will accept a session" (`docs/attach-mode.md:100-101`). Recorded demo scores of 0.9 on two reCAPTCHA v3 score pages are described as "earlier runs … not a verification of the current release" (`docs/launch-identity.md:94-103`).

---

## 13. Recording and diagnostics

**Recording — code** (`src/recording.ts`): CDP screencast JPEG frames piped to an FFmpeg child process (`image2pipe` → libx264 `veryfast`, CRF 28, `zerolatency`, fragmented MP4; or libvpx realtime for `.webm`) (`:111-120`). Defaults fps 60, 1280x720, quality 80, max duration 300 s (cap 3,600 s), pixel cap 8,294,400 (`:28-42`). File opened `wx` 0600; byte-limited; capture queue of 4 frames / 16 MiB; one recording per session; 50 MiB reserved from the artifact quota; no audio; FFmpeg is not bundled (`docs/recording.md:69-73`). Chosen over Playwright video because that is fixed at 25 fps and needs a new context (`docs/performance-audit.md:102-110`). Exposed as `recording.*` in snippets, `betterwright record …`, and MCP `browser_record`.

**Diagnostics**:
- `betterwright doctor` / MCP `browser_doctor`: readiness by area (runtime, browser, agent integration, model backends, credentials), `--json`, exit code tracks readiness (`docs/cli.md:58-67`).
- `betterwright mcp --check`: verifies the MCP peer and the browser are present.
- Per-call: snippet `console.*` captured (20 x 300 chars); page console and errors via `page.consoleMessages()` / `page.pageErrors()` (200 retained per page) or scoped `page.on("console"|"pageerror")` (`docs/browser-api.md:647-713`).
- `events` (page lifecycle, downloads, dialogs), `warnings` (profile fallback, backend, dropped Chromium switches, ad-block notes, provider notices), `challenges`.
- `site.requests()/assets()/read()/request()`: recent same-origin request metadata and guarded same-origin HTTP with a 1 MB body cap (`docs/browser-api.md:190-205`).
- `controls.inspect()`, `media.inspect()`, `overlays.dismiss()`.
- Vault `audit.jsonl` (metadata only); `daemon.log`; `betterwright sessions`.
- The Pi extension can write a JSONL step trace with screenshots (`BETTERWRIGHT_PI_TRACE_DIR`).

No HAR export, no Playwright trace (context `tracing` is removed from the facade).

---

## 14. Built-in agent (`betterwright exec`, `runAgentTask`)

**Loop — code** (`src/agent.ts:699-1560`, constants `:56-85`):
- System prompt = harness preamble + `agentSystemPrompt(guardrails)` + bodies of skill packs whose keywords match the task (`:226-242`).
- Tools: `browser` (code, note), `done`, `login` (when a vault exists), `ask`, `live_view`, `handoff` (when a human surface exists) (`:347-360`).
- **No step cap.** Bounds: 30 min wall clock, 1,000,000 transcript chars, default 4,096 output tokens per turn (`:56-58`).
- Observation = compact JSON with only non-empty fields: `ok, result, error, pendingCredential, console, pages, challenges, skills, warnings, webagents, ui, screenshots, recordings, duration_ms` (`:376-406`).
- **Single-call finish**: if the snippet returns `{finalAnswer: "…"}` on an ok run, the task ends without another model turn (`:465-476`).
- **No-progress detector**: error text normalised (lowercased, digits → `#`, 200 chars); 3 identical failures in a row add a warning, 5 end the run with `reason:"no_progress"` (`:84-85, :444-463`).
- Model retries: 3 attempts, 500 ms base, 8 s max, honours Retry-After (`:157-159, :573-623`).
- For tasks matching the `checkout-verification` skill, a second "completion check" call asks the same model to verify the answer against fresh read-only evidence, max 3 checks (`:248`, `docs/agent.md:97-131`).
- Result: `{ok, answer, steps, reason, toolCalls, usage{inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens, context}, durationMs, timing{modelMs, toolMs}, proof, recordings}`; `reason` in `done | answered | stopped | interrupted | timeout | context_limit | no_progress | max_tokens | refusal | model_error` (`docs/agent.md:45-64, :133-139`).

**Models — code + docs**: pluggable `{name, complete({system, messages, tools}) → {text, toolCalls, stopReason}}`. Built-in adapters: Anthropic SDK (`claudeModel` `:2110`), OpenAI Chat Completions (`openaiModel` `:2277`), OpenAI Responses (`:2452`), Codex via ChatGPT OAuth (`:2571`), Grok (`:2616`); endpoint presets OpenRouter, Cerebras, Ollama, vLLM, custom (`:168`). Bare model ids are resolved by probing catalogs; ambiguity is an error. Default effort `low`. `betterwright --local` installs a hardware-matched local model and runtime (`docs/local-ai.md`). The model ids in the docs (`gpt-5.6-sol`, `claude-opus-5`, `grok-4.6`, `qwen3.8:27b`) are quoted as written there; I did not check that they exist.

**Prompts**: full text at `src/prompt.ts:15-41` (operator guidance, ~27 lines), `src/agent.ts:204-222` (preamble), `:244-284` (tool descriptions). Character of the guidance: "The user's request authorizes ordinary steps: sign-in, signup, forms, purchases. Do not add confirmation or refuse them unless a guardrail requires it" (`src/prompt.ts:18`). Limits are opt-in `Guardrails` — `confirmBeforePurchase, confirmBeforeIrreversible, forbidPurchases, forbidAccountCreation, spendingLimit, extraRules, passwordManager` — and are prompt text only (`:56-88`); the docs say so: "It does not, by itself, stop anything" (`docs/agent-prompt.md:77-80`).

---

## 15. Electron adapter — code

`betterwright/electron` (`src/electron.ts`, `src/electron-connection.ts`, `src/electron-cdp.ts`):
1. `configureElectronNetwork()` before `app.ready`: `disable-quic` and `force-webrtc-ip-handling-policy=disable_non_proxied_udp` (`src/electron.ts:8-12`).
2. `createElectronHostTarget({contents, signal, uploadFiles, cookieImport, expectAgentInput})` returns a `hostTarget` passed to `new BetterWright({hostTarget})`.
3. On connect (worker → client RPC `host_connect`, `src/worker.ts:1346-1353`, `src/client.ts:999-1026`): requires a **dedicated, unleased Electron session**; denies downloads via `will-download`; `session.setProxy({proxyRules: <guard SOCKS>, proxyBypassRules:"<-loopback>"})`; `closeAllConnections()` (`src/electron.ts:23-41`).
4. Attaches `webContents.debugger` (CDP 1.3), `Target.attachToTarget` flat, then starts a **loopback HTTP/WebSocket server** on `127.0.0.1:0` that accepts exactly one client at `/browser` with `Authorization: Bearer <32 random bytes hex>` (constant-time compare, no `Origin` allowed) and proxies CDP through an allowlisting `BetterwrightCdpTarget` (`src/electron-connection.ts:17-66, :88-127`). The worker then `connectOverCDP`s to it with `noDefaults` and requires exactly one context and one page (`src/worker.ts:1463-1472`).
5. Tab lifetime stays with the host; `browser.close()` only disconnects. Downloads denied, credential capture off, vault metadata-only on host targets (`src/client.ts:655-658, :1050-1052`). Abort via the host's `AbortSignal` (human-takeover detector).

---

## 16. Configuration reference

### Constructor options (`new BetterWright({...})`) — `src/client.ts:498-584`, `docs/javascript.md:12-30`

| Option | Default |
| --- | --- |
| `home` | `$BETTERWRIGHT_HOME` or `~/.betterwright` |
| `profile` | none (single default profile) |
| `policy` | `new NetworkPolicy()` (permissive except metadata) |
| `vault` | built-in local vault; `false`/`null` disables; custom `{handleRequest, redact?}` |
| `credentialCapture` | `true` when a vault exists |
| `allowCredentialOverwrite` | `false` |
| `provider` | none (managed fork); `{executablePath}` / `{cdpUrl, headers}` / `{provider, apiKey, sessionOptions}` / array = fallback chain |
| `hostTarget`, `hostUploadFiles` | none (Electron) |
| `headless` | `"auto"` (headed if a display exists); the CLI defaults to headless |
| `headedInvisible` | `false` |
| `adBlock` | `true` |
| `fingerprintNoise` | `true` |
| `publicSearchPolicy` | `"allow"` (`:171`; the worker's own fallback is `"block"` — `src/worker.ts:1190` — only reachable if the client omits it) |
| `searchMinIntervalMs` | `0` |
| `downloadPolicy` | `"ask"` |
| `stealthRuntimeFix` | `false` |
| `launchIdentity` | `true` |
| `upstreamProxy` | none (`http://` or `socks5://`) |
| `geoip` | `false` (looks up `ip-api.com` through the upstream — `src/launch-identity.ts:145`) |
| `locale`, `timezone`, `platform` | host values |
| `chromiumArgs` | `[]` |
| `parkBackgroundPages` | on |
| `defaultTimeout` | 30 s (min 5) |
| `liveView` | `{host: 0.0.0.0, port: 0, interactive: true, quality: 60, maxWidth: 1440}` |

Internal, not configurable: `outputLimit` 12,000; `maxArtifactBytes` 100 MiB; `maxDownloadBytes` 50 MiB; `pageIdleTimeoutMs` 1,800 s (`src/client.ts:659-662`).

`NetworkPolicy`: `allowPrivateNetwork` (true), `allowLoopback` (true), `allowHosts` ([]), `blockHosts` ([]), `custom` (none).

### CLI flags

Shared by `run`, `repl`, `exec`, console (`docs/cli.md:14-35`): `--session`, `--profile`, `--headed`, `--headed-invisible`, `--no-daemon`, `--browser`, `--browser-key`, `--session-id`, `--ad-block`/`--no-ad-block`, `--stealth`, `--block-private-network`, `--block-loopback`, `--allow-host`, `--block-host`, `--no-launch-identity`, `--upstream-proxy`, `--geoip`, `--locale`, `--timezone`, `--platform`.

`run`: `-c`, `--close`, `--pretty`, `--no-auto-ui`, `--approve-downloads`. `exec`: `--model`, `--base-url`/`--endpoint`, `--api-key-env`, `--protocol`, `--effort`/`--reasoning`, `--allow-insecure-model-endpoint`, `--live-view`, `--fresh`, `--stdin`, `--close`. `view`: `--expose`, `--host`, `--port`, `--public-host`, `--watch-only`, `--set-password`, `--clear-password`. `record start|restart`: `--fps`, `--max-width`, `--max-height`, `--quality`, `--max-duration`.

Commands: `init, setup, update, doctor, configure, run, repl, exec, view, record, sessions, close, cookies, vault, boxes, auth, models, skill, skills, mcp, local` and a bare `betterwright` interactive console (`bin/cli-main.ts:2305-2401`).

### Environment variables (`docs/environment.md`)

| Variable | Default | Effect |
| --- | --- | --- |
| `BETTERWRIGHT_HOME` | `~/.betterwright` | state directory |
| `BETTERWRIGHT_PROFILE` | unset | named identity (only way for MCP) |
| `BETTERWRIGHT_SESSION_TTL_SECONDS` | 900 | session idle TTL |
| `BETTERWRIGHT_ORPHAN_GRACE_SECONDS` | 30 | unwatched-run grace; 0 disables |
| `BETTERWRIGHT_NO_DAEMON` | unset | 1 = one-shot browsers |
| `BETTERWRIGHT_BACKEND` | `auto` | `chromium-fork` requires the fork |
| `BETTERWRIGHT_CHROMIUM_PATH` / `_ROOT` | unset | explicit fork binary / artifact root |
| `BETTERWRIGHT_CHROMIUM_ARGS` | unset | extra switches (reserved ones rejected) |
| `BETTERWRIGHT_CDP_URL` | unset | attach to a CDP endpoint |
| `BETTERWRIGHT_HEADLESS` | unset | MCP only: 0 headed, 1 headless |
| `BETTERWRIGHT_DISPLAY` | detected | force display detection |
| `BETTERWRIGHT_LOCALE`, `BETTERWRIGHT_TIMEZONE` | unset | MCP identity |
| `BETTERWRIGHT_BLOCK_PRIVATE_NETWORK`, `BETTERWRIGHT_BLOCK_LOOPBACK` | unset | MCP policy hardening |
| `BETTERWRIGHT_ALLOW_HOSTS`, `BETTERWRIGHT_BLOCK_HOSTS` | unset | comma-separated |
| `BETTERWRIGHT_PUBLIC_SEARCH_POLICY` | `allow` | `block` refuses Google/Bing/DDG result pages |
| `BETTERWRIGHT_DOWNLOAD_POLICY` | `ask` | `allow` / `deny` |
| `BETTERWRIGHT_AD_BLOCK` | on | 0 disables |
| `BETTERWRIGHT_PARK_BACKGROUND_PAGES` | on | 0 disables parking |
| `BETTERWRIGHT_STEALTH_RUNTIME_FIX` | off | 1 = patchright driver |
| `BETTERWRIGHT_FFMPEG_PATH` | PATH | FFmpeg binary |
| `BETTERWRIGHT_LIVE_VIEW` | unset | MCP: allow non-loopback bind |
| `BETTERWRIGHT_LIVE_VIEW_EXPOSE` / `_HOST` / `_PORT` / `_PUBLIC_HOST` / `_PASSWORD` | `lan` / `0.0.0.0` / ephemeral / LAN IPv4 / unset | viewer hosting |
| `BETTERWRIGHT_TIMEOUT_SECONDS` | 120 (MCP) | per-snippet timeout |
| `BETTERWRIGHT_WORKER_START_TIMEOUT_MS` | 15000 | worker ready handshake |
| `BETTERWRIGHT_VAULT_ALLOW_NON_INTERACTIVE` | unset | allow `--reveal` to a pipe |
| `BETTERWRIGHT_MODEL`, `_MODEL_BASE_URL`, `_MODEL_API_KEY`, `_MODEL_PROTOCOL`, `_CLAUDE_MODEL`, `_CODEX_MODEL`, `_GROK_MODEL`, `_CEREBRAS_MODEL` | — | agent model selection |
| `BETTERWRIGHT_PI_*` (START_URL, MAX_STEPS, SESSION, TRACE_DIR, AUTO_SCREENSHOT, TIMEOUT_SECONDS, DOWNLOAD_POLICY, REQUIRE_EVIDENCE) | — | Pi extension |

Provider keys: `BROWSER_USE_API_KEY, KERNEL_API_KEY, BROWSERBASE_API_KEY, STEEL_API_KEY, ANCHOR_API_KEY, HYPERBROWSER_API_KEY, BROWSERLESS_API_KEY, BRIGHTDATA_BROWSER_AUTH, OXYLABS_BROWSER_AUTH` (`docs/browser-providers.md:201-211`). Model keys: `ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, CEREBRAS_API_KEY, XAI_API_KEY/GROK_API_KEY, OLLAMA_API_KEY, VLLM_API_KEY` and matching `*_BASE_URL`.

`<home>/config.json` (0600): `browser.default`, `browser.fallbacks`, `browser.accounts`, custom providers; `liveView.{expose, host, port, publicHost, passwordHash}`.

On-disk layout: `docs/architecture.md:149-169`.

---

## 17. Benchmarks — full read of `benchmarks/`

Eleven directories. Headline: **there is no reproducible comparison against Playwright MCP, agent-browser or browser-use anywhere in the repo.** Two documents compare against an unnamed "reference" CLI and both state that nothing comparative should be concluded. Everything else is BetterWright-versus-earlier-BetterWright, or a self-judged task benchmark. I read every README/REPORT in full plus `online-mind2web/results.json` and `ad-blocking/results.csv`; other raw JSON files were not cross-checked against the report text.

### 17.1 `browser-agent-headtohead/` — runtime vs unnamed reference (recorded 2026-07-18)
Harness: `run.sh`, hand-written JS, login-free tasks. Environment: macOS, "BetterWright CloakBrowser 145 headless" — i.e. **before BetterChromium and before the session daemon**; stale.
- Cold one-shot CLI call (median of 3): BetterWright ~700 ms, reference ~535 ms.
- Warm per-op: BetterWright 68-109 ms, reference ~90-130 ms (reference figure estimated, not separately reported).
- First op in a BetterWright session ~550 ms.
- End-to-end with Pi coding agent + BetterWright vs the reference's agent, both `gpt-5.6-sol` low: HN top story 20.3 s vs 7.3 s; Eiffel Tower height 22.4 s vs 10.3 s; both correct.
- Disclaimer: "The reference runtime is not named, not vendored, and not version-pinned here, so its numbers cannot be audited" (`REPORT.md:8-13`).
- Useful finding: the run exposed the password-in-snapshot leak that led to `redactPasswordValues`.

### 17.2 `exec-headtohead/` — built-in agent vs unnamed reference agent (2026-07-19)
"This is not a benchmark, and it is not reproducible as published." 15 scenarios, single runs, `gpt-5.6-sol` low, hand-assessed, BetterWright tuned against the same 15 scenarios over three rounds. Round-3 times (BetterWright / reference): 5.3 s/7.6 s · 18.0/8.6 · 7.5/9.1 · 7.0/11.1 · 24.8/10.3 · 9.2/7.7 · 89.7/14.0 · 18.5/13.3 · 25.6/17.9 · 14.6/12.3 · 29.2/39.4 · 87.1/113.5 (site down) · 50.7/64.2 · 24.4/17.9 · 22.5/150.0 (timeout). Hand-assessed correctness 14/15 vs 12/15. Token usage, BetterWright only: trivial task 1 step, ~2.6K input, ~0.1K output; checkout 5 steps, ~8-10K uncached input, ~15-20K cache read, ~0.9K output. Real output of the exercise: three fixes — single-call `finalAnswer`, a password rule that distinguishes task-supplied from vault credentials, and backoff on transient 5xx.

### 17.3 `online-mind2web/` — task success (2026-07-15)
Harness: Pi Coding Agent + BetterWright extension (`runner.ts`), local strict multimodal LLM judge (`judge.ts`); agent and judge both `openai-codex/gpt-5.6-sol`, reasoning high, 100 browser steps, concurrency up to 32.
- 300 tasks: **278/300 = 92.7%** (easy 80/81 = 98.8%, medium 134/143 = 93.7%, hard 64/76 = 84.2%).
- 50-task sample: development baseline 26/35 = 74.3%, after targeted iterations 34/35 = 97.1%, frozen holdout 13/15 = 86.7%, combined 47/50 = 94.0%.
- Caveats in their own words: "an iterative best-validated campaign, not a one-shot run"; "not an official Online-Mind2Web human evaluation or leaderboard score"; the judge is the same model as the agent. The cleanest number is the untouched holdout, 13/15.

### 17.4 `odysseys/` — long-horizon tasks (2026-07-23)
Built-in `exec` agent, `gpt-5.6-sol` high, 90 min per task, judge `gpt-5.6-luna`. **Partial: 24 of 200 attempted, 23 judged, unstratified.** Perfect rate 8.7% (2/23); rubric average 67.5% (easy 54.8%, medium 80.0%, hard 71.5%); mean 10.0 min and ~34 steps per task. Paper figures quoted for context only: Opus 4.6 44.5%, GPT-5.4 33.5% perfect — "not like-for-like". Dominant failure: claims without visual evidence, because the agent is tuned for few round-trips.

### 17.5 `perf/` — per-action overhead, loopback fixtures only
Harness `run.ts`: A per-action latency (100 samples of `return page.title()`), B page load with 50 subresources across 4 origins counting guard RPCs at the stdio boundary, C per-action latency with 10/24 cross-site iframes. Linux x64, 8 CPUs, a background process held ~150% CPU throughout.
- Baseline (1.6.2): A p50 7.60 ms (p95 11.31); A' 6.45 ms; B page load 715.8 ms; C 36.68 ms (10 iframes), 60.57 ms (24 iframes); guard RPCs per load: route 51, transport p50 44 (36-48), total 95.
- Phase A (worker-side guard cache): route 51 → p50 1 (mean 2.0, -96.1%); transport 44 → p50 0 (mean 0.8, -98.1%); wall time unchanged (713.8/716.2 ms).
- Phase B (staged challenge scan): 10 iframes 36.68 → 8.99/8.64 ms (-74 to -76%); 24 iframes 60.57 → 11.64/9.38 ms (-81 to -86%); iframe tax +30.2 → +1.5/+1.7 ms and +54.1 → +4.1/+2.4 ms; A' rose 0.5-1.1 ms.
- Later audit (`docs/performance-audit.md`, Chromium 151, Ryzen 9 7950X3D): quiet action p50 4.60 → 2.62 ms; 10 iframes 4.57 → 2.94 ms; 24 iframes 4.85 → 3.25 ms; heavy page 601.58 → 600.57 ms; 1,000 warm actions used ~25% less CPU.

### 17.6 `efficiency/` — harness overhead (1.7.0 → 1.7.1, no browser, no model)
2,000-turn agent loop 906.3 → 17.2 ms (52.8x); transcript 750,009 → 476,009 chars (-36.5%); **one successful observation 44 → 15 tokens (174 → 53 chars, cl100k)**; MCP observation 43 → 15 tokens; 3,000-line replacement diff 18.8 → 1.3 ms, RSS 66.0 → 45.9 MiB; adversarial one-common-line diff 15.7 → 33.9 ms (slower, bounded memory).

### 17.7 `navigation-context/` — observation size, two commits
10 measured pairs per workload, macOS arm64. Median ms (baseline → candidate) and piped characters: article extraction 46.4 → 46.8, 8,855 → 2,740 chars; form submission 392.3 → 357.9, 1,864 → 973; table filtering 83.5 → 84.2, 1,471 → 744; delayed content 859.0 → 239.4, 318 → 236; explicit directory 54.2 → 48.0, 3,056 → 837. Observations 25.8-72.6% smaller. The delayed-content win comes from `domcontentloaded` instead of `load`.

### 17.8 `ui-batching/` — batch vs individual calls
Runtime (no model), median: form 532.7 → 106.6 ms (-80.0%, 6 calls → 2); deferred 1324.5 → 224.3 ms (-83.1%, 4 → 2); wizard 674.0 → 331.6 ms (-50.8%, 5 → 2); frame 519.5 → 120.4 ms (-76.8%, 5 → 2). 160 measured cases passed.
Model trials (DeepSeek V4.1 Flash, 4 workloads x 3 repetitions): strict success 6/12 → 12/12; mean 21.16 → 16.89 s; input tokens 599,537 → 403,484; output 26,665 → 15,856; tool calls 76 → 56; API cost $0.025228 → $0.016768. "12 trials per build, not 12 distinct tasks."

### 17.9 `ad-blocking/` — see section 11.

### 17.10 `runtime-efficiency/`, `snapshot-compression/` (numbers in `docs/runtime-performance.md`, `docs/performance-audit.md`)
Action-directory scan with 36 controls sharing a form: 52.6 → 5.3 ms. GPU-less Linux with SwiftShader scoped to WebGL: process CPU 13.435 → 3.035 s (-77.4%). Snapshot compression of 4,000 adjacent paragraphs: 1,546.97 → 1.693 ms, peak RSS ~286 → ~68 MiB, 23,225 output comparisons identical. Recording: MP4 used 16-40% less encoder CPU and ~12% less memory than WebM; file 59% smaller for text, 41% larger for motion. CLI startup ~42-44 ms.

### 17.11 `browser-process/`, `stealth-bench/` — harness only, **no results committed**
`browser-process`: candidate-vs-baseline startup, navigation, RSS/PSS, CPU, renderer count, long-session growth on loopback fixtures. `stealth-bench`: applies Browser Use's encrypted 80-task Stealth Bench to BetterWright, treats CAPTCHAs as blocked, stores only verdicts. No scores exist in the repo for either.

### What is absent
No token-per-task comparison with any other tool, no latency comparison with Playwright MCP, no success-rate comparison under matched conditions, no snapshot-size comparison against raw Playwright output on real sites.

---

## 18. What the tests guarantee

135 files, 46,225 lines. Runner: Node's `node:test` under Bun; browser suites need `BETTERWRIGHT_REQUIRE_BROWSER=1`. CI: lint, typecheck, build check, unit tests, type tests, package check, full browser suite + FFmpeg on Ubuntu, unit tests cross-platform, `bun audit` (`.github/workflows/ci.yml`). A custom oxlint plugin bans module mocking (`tools/oxlint/anti-slop/rules/no-module-mocking.ts`).

Black-box cases against the built binary (`tests/e2e/*-cases.ts`), by title:
- Sandbox: no Node globals/process/module loading; CDP, routing and context mutation inaccessible; constructor chains cannot compile host code; request/response wrappers hide cookie headers; `file:`/internal navigations fail; uploads reject outside paths, traversal and symlinks; script/stylesheet paths confined; writes confined to artifacts (`security-cases.ts:18-214`).
- Network: metadata blocked despite allowlisting and never reaches a local upstream; private-network and loopback denial incl. numeric, `localhost` and mapped-IPv6 forms; a blocked host cannot be reached via redirect (`:236-300`).
- Vault: metadata-only exposure, owner-only encrypted files; fill omits secrets and submits only on request; secrets scrubbed from values, keys, console history and errors; exact-origin / host / never matching; overwrite denied; ambiguous forms fail closed; generated credentials pending until commit; discard; recovery after a failed snippet across sessions; rotation in place (`:337-667`).
- Downloads: concurrent sessions do not share a per-run approval (`:704`).
- Recording: MP4 preserves page state and contains changing frames; restart; CLI flushing (`:754-810`).
- CLI: help/version are read-only; snippet input modes; compact vs pretty JSON; failure envelope + exit status; named sessions keep separate state; `--close`; configure persistence and key masking; vault refuses piped master passwords (`cli-cases.ts:36-374`).
- MCP: capability negotiation and clean shutdown at EOF; JSON-RPC errors; contradictory batch/record arguments rejected; state retained across calls; failures carried in envelopes; download denial even when arguments claim approval (`protocol-cases.ts:106-232`).
- Agent: `exec` against a local OpenAI-compatible mock (`:245-307`).

Unit-level, read directly: snapshot compression/filter/diff/annotation (`tests/node/snapshot.test.ts`), automatic-UI budget (`automatic-ui.test.ts`), 714 lines of policy vectors, `challenge-scan-gate.test.ts` proving the staged scan only diverges from the full scan in the documented over-budget case, `guard-proxy.test.ts` (1,119 lines), `vault.test.ts` (2,061), `credential-fill.test.ts` (2,133), `daemon-resilience.test.ts`.

Optional live-site CAPTCHA tests explicitly do not assert a solve.

---

## 19. Ideas a Python engine could adopt

Python specifics I did not check: whether the Python Playwright build you pin exposes `aria_snapshot(mode="ai")` with `[ref=eN]` markers and the `aria-ref=` selector engine. BetterWright relies on both at Playwright 1.61.1. **UNVERIFIED for Python — check the pinned version's docs before designing around it.** If absent, refs must be produced another way (CDP accessibility tree + backend node ids).

### Small
1. **Refuse over-limit snapshots instead of truncating**, returning the actual size and scoping hints (`src/worker-snapshots.ts:126-141`).
2. **Scrub password field values from every snapshot** and register them in a redaction set (`:28-59`).
3. **Omit empty fields from the model-facing observation and emit compact JSON when piped** — their measured saving was 44 → 15 tokens per successful call.
4. **Auto-return for a trailing expression** (Python analogue: parse with `ast`, rewrite a final `Expr` into a return).
5. **Default navigation to `domcontentloaded` and a 5 s action timeout**, with explicit overrides.
6. **Untrusted-data envelope** around spilled output and a `trust: "untrusted_external_data"` label on page-controlled results.
7. **Download approval as transport metadata** the model cannot set; a separate download tool is the grant.
8. **`effectMayHaveCommitted`** on cancelled/timed-out actions, plus "never replay a non-idempotent action" in the prompt.
9. **Repeated-failure signature** (normalise digits, 3 → warn, 5 → stop).
10. **Screenshot intent kinds** (`proof` / `question` / `debug`) with a `question` page-hold.
11. **Failure evidence**: on error attach up to four short visible status/alert excerpts gathered within 200 ms.
12. **Metadata floor as a constant plus a JSON vector file** as the conformance suite for the policy.
13. **Reserved-flag list** for caller-supplied Chromium switches (proxy, debugging port, user-data-dir) with drop-and-warn for collisions.
14. **Single-call finish** (`finalAnswer`) if you ship an agent loop.

### Medium
15. **Snapshot compression pipeline** — the nine rules in section 3.1, as pure text functions with unit tests.
16. **Interactive filter with context** (keep status/alert, table headers, short row text) and **keyed diff** with a line cap.
17. **Semantic UI batch** with exact-one-match targets, write opt-in, mandatory final asserted read or explicit `observe`, stale-success guard, no rollback but completed-id reporting.
18. **One-time compact action directory per origin+path** under a hard character budget that never shortens a target.
19. **Session daemon**: per-session FIFO lanes, config-signature handshake, idle TTL, orphan grace, replay buffer for reattach, fallback to one-shot with an explicit `session persistence unavailable` warning.
20. **Profile lock with heartbeat lease** and an ephemeral-profile fallback surfaced as `profileMode`.
21. **Guard decision cache** with a client-asserted `cacheable` flag, 5 s TTL, never for navigations; flush on any non-cacheable answer.
22. **Staged challenge scan** (cheap main-frame read; per-frame read only on a signal) — removed a 30-54 ms per-action tax in their fixture.
23. **Page parking** between calls for headless sessions.
24. **Credential vault**: single AEAD blob, PSL-based base-domain gating (`tldextract`/`publicsuffix2` in Python), metadata-only RPC surface, two-phase generated passwords, bounded redaction set that fails closed.
25. **CDP screencast → FFmpeg recording** with bounded queues.
26. **Transcript elision** for resumed sessions (replace stale observations with a stub).
27. **Skill packs** matched by URL and task keywords.
28. **Provider fallback chain** that releases a billed remote session before trying the next candidate.
29. **Ad blocker inside the policy route handler, after the policy decision** (Python has `adblock`/Brave bindings; not Ghostery's JS engine).

### Large
30. **Loopback SOCKS guard proxy with DNS pinning** (resolve once, authorize every address, dial the literal). This is the only control that survives a sandbox escape and it also covers WebSockets without Playwright interception. Needs an asyncio SOCKS5 server, upstream chaining, and careful failure caching.
31. **Live view + handoff server** (screencast over WebSocket, `Input.dispatch*` back, token + optional password, survives worker restart).
32. **Process split client ↔ worker** with RPC callbacks answered mid-execution.
33. **Electron/host-owned tab adapter** with a single-client, bearer-authenticated, allowlisting CDP proxy.
34. **Maintaining a Chromium fork** — not recommended; see risks.

### Design lessons from their mistakes
- Truncation was replaced by refusal after truncated trees were read as complete.
- A refused snapshot must not become the diff baseline.
- Per-frame work on every action is expensive; gate it.
- Playwright's SOCKS `proxy` option injects a flag that shows an infobar; pass the proxy switches yourself.
- `fe80::/10` must be matched on bits, not on a `fe80:` text prefix.
- An agent tuned for few round-trips under-collects evidence (Odysseys result).

---

## 20. Risky parts

### Stated by the authors
1. **`node:vm` is not a security boundary** (`docs/architecture.md:78-81`, `README.md:207-209`). Python has no equivalent in-process sandbox at all; running model-authored code needs a separate process with OS-level confinement.
2. **Network policy is permissive by default** — private networks and loopback are reachable (`README.md:197-205`).
3. **Remote CDP / cloud browsers are outside the transport guard**: no metadata floor at transport level, no DNS-rebinding protection (`SECURITY.md:12-15`).
4. **Vault secrecy is limited**: the filled value is in the DOM; same-user file access defeats the default key file; redaction is literal-match and can be bypassed by transforming the value (`SECURITY.md:18-23, :40-44`).
5. **Sessions are not a security boundary**; any same-user process can drive any session through the socket (`docs/sessions.md:120-127`).
6. **Guardrails are prompt text**, "not a payment firewall" (`docs/agent-prompt.md:113-117`).
7. **Live view over LAN is plain HTTP**; token, password and stream travel unencrypted; the token-bearing URL enters model context (`docs/live-view.md:195-209`).
8. **`allowHosts` is not an exclusive allowlist** (`docs/network-policy.md:71-74`).
9. **No undetectability or CAPTCHA-acceptance guarantee** (`README.md:192-195`).

### My assessment — detection evasion and legal exposure
10. **CAPTCHA solving is a headline feature and the default instruction to every model** (section 10). Highest-risk item.
11. **BetterChromium is an anti-detect browser**: forced `navigator.webdriver=false`, removed headless UA marker, Chrome brand spoof, seeded canvas/audio/WebGL noise, GPU-string spoof on software GL, inspector-timing concealment, optional full macOS mask, and (documented but absent from the checked-in patches) CreepJS-specific presence changes (section 12). Shipping or depending on it means distributing fingerprint-spoofing software whose binary is not fully reproducible from the repository.
12. **`patchright-core` stealth driver**, **human-shaped input adapted from CloakBrowser** (`src/human.ts:1-23`), **`research/warm-profile.ts`** (ages a profile with fake browsing), **upstream residential proxy + geo-matched locale/timezone**, and the decision not to intercept WebSockets specifically to avoid bot-defense detection (`src/worker.ts:1159-1163`). `research/README.md:49-56` carries the only scope statement: not "an invitation to defeat access controls".
13. **Cookie Sync** copies authentication cookies out of the user's Chrome/Firefox/Safari profiles via a native reader; the Windows opt-in uses "unprivileged reflective injection into a newly spawned browser process" which "endpoint security software can flag"; cookies can be pushed to third-party cloud browsers (`docs/cookie-sync.md:130-143, :158-183`).
14. **Autonomy-by-default prompt**: sign-in, signup and purchases are authorized by the request with no confirmation unless a guardrail is set (`src/prompt.ts:18`).
15. **Silent credential capture** of model-typed logins, on by default.
16. **`geoip`** contacts `ip-api.com` over plain HTTP through the upstream proxy (`src/launch-identity.ts:145`).

### Project risk
17. 11 weeks old, ~1 release/day, two main committers plus AI agents, 46k lines of tests but a 2,847-line worker entrypoint. Benchmarks are self-reported, partly stale (CloakBrowser era), partly tuned on their own test set, and the only cross-tool comparisons are against an unnamed tool.
18. Stale comments found while reading: `src/mcp-server.ts:44` (live-view default host), `src/worker.ts:108-113` (comment says 10 s, constant is 5 s), line references inside `benchmarks/perf/REPORT.md`. Minor, but a sign that docs and code drift.

### Not verified
- Form-detection heuristics in `src/credential-fill.ts`, capture sensor in `src/vault-sensor.ts`/`vault-capture.ts`, WebAgents/WebMCP internals, local-AI installer, cookie-sync internals, Electron CDP allowlist contents, most of `live-view.ts`: described from docs.
- Chromium patch: I read the UA, `navigator.webdriver` and inspector hunks and confirmed by grep that the canvas/audio noise, Intel GPU string, `ActiveText` and `deviceMemory` hunks exist. The macOS-mask geometry, WebGPU and V8 hunks are described from `docs/chromium-fork-patches.md`. Whether the published binaries were built from exactly these patches is UNVERIFIED (see the mismatch in section 12).
- Benchmark figures other than Online-Mind2Web totals and the ad-blocking rows: taken from the report text, not recomputed from raw JSON.
- Whether BetterWright actually runs, and any of its performance or stealth claims: nothing was executed.
