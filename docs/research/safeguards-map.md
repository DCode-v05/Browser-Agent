# Safeguards map for bap-browser

Researched on the web on 2026-10-07. Builds on four reports already in this folder
(`anthropic-safeguards.md`, `mcp-security.md`, `prompt-injection.md`, `auto-mode.md` sections 1-3)
and on two reports being written alongside this one (`web-threats.md`, `fallbacks.md`, both still
skeletons at the time this was written: headers only, no content). This report does not redo their
deep dives; it places every category of safeguard a serious computer-use or browser-agent product
uses on one map, says whether `bap-browser` has it today, and points at the report that covers each
one in depth.

Every vendor and framework reviewed here — Anthropic, OpenAI, Google, Microsoft, Amazon, the cloud
browser vendors, and OWASP/NIST/MITRE/CSA — converges on the same shape: no single layer stops a
fooled or misused agent, so shipped products stack isolation, narrow default permissions, human
confirmation on consequential and financial actions, content classifiers, egress and site limits,
audit logs, and resource or spending caps, then test the stack against adaptive attackers rather
than trusting a fixed benchmark. `bap-browser` already has a real share of the structural layers
that do not depend on a model behaving correctly: an address policy that canonicalises every address
spelling before judging it, consequential-action confirmation that cannot be bypassed by a site
grant, approval timeouts that default to deny, settings that a person or deployment can only
tighten, redaction of passwords and tokens from every result and log, a human hand-off for CAPTCHAs
and sign-ins, and per-site permission enforced on the person's own machine for take-over Chrome. It
is missing several layers that every mature competitor adds once real users and real money are
involved: a scanner on incoming page content, a check on what the agent sends out (the "lethal
trifecta" pattern Willison and Anthropic both name), a per-task site scope, a spending cap, an
audit-log retention policy, supply-chain controls for the extension, and any ongoing red-team or
adversarial-evaluation practice. None of these require the engine to own a model; nearly all are
deterministic checks the core can add directly, which is exactly the kind of safeguard this engine
is already built to hold.

---

## The map

One row per safeguard category. "Has it today" was checked by reading the spec and the code named;
"not checked" means exactly that, not "no". Source kinds: **V** vendor docs/blog, **S** system card,
**F** framework/standard, **P** paper, **T** third party, **C** our code/spec (checked directly).

| # | Category | Protects against | Concrete controls seen (vendor) | Frameworks (ids) | `bap-browser` today | Depth report |
|---|---|---|---|---|---|---|
| 1 | Prompt injection (content-level) | Hidden/visible page text steering the agent | Classifiers on tool results, RL-trained refusal, spotlighting, site/action limits (Anthropic, OpenAI, Google, Perplexity, Brave) | OWASP LLM01:2025; MITRE ATLAS | **Partly.** Hidden text (`display:none` etc.) left out of snapshots; page content declared untrusted in tool/server instructions (`docs/bap-browser-spec.md` 5.4, 8.5). No classifier, no marked boundary, no opacity/offscreen/contrast checks yet (8.5 names these as later items) | `prompt-injection.md` |
| 2 | MCP/tool-server attacks (poisoning, rug pull, shadowing, confused deputy, token passthrough) | A malicious client or co-hosted server abusing our tool surface | TOFU pinning, static descriptions, per-client consent (MCP spec, Invariant, Trail of Bits) | OWASP MCP Top 10 (MCP01-10:2025) | **Partly.** Tool descriptions are static for a session (`tools/registry.py`, `tools/browser_tools.py`); no hash/pin a client can check; we are the server so confused-deputy/passthrough mostly do not apply | `mcp-security.md` |
| 3 | Transport/service security (Origin, Host, DNS rebinding, bearer token) | A web page or stray script reaching the local service | Origin/Host checks, loopback bind, bearer token (MCP spec, Python SDK, CVE-2025-9611, CVE-2025-52882) | OWASP MCP Top 10 | **Yes.** `TrustedHostMiddleware` on Host (`service/app.py`); WebSocket `Origin` checked against the viewer's own origin or `viewer.embed_origins`; bearer token via `hmac.compare_digest`; extension bridge checked against the extension's own origin (`service/app.py` `extension_socket`); loopback-only by default (`server.host`) | `mcp-security.md` |
| 4 | Network egress / address policy | Navigating to private networks, cloud metadata, blocked domains | Domain allowlists, private-range blocking, metadata blocking, proxy-only egress (Anthropic, Claude Code sandboxing, Managed Agents) | OWASP LLM-adjacent SSRF guidance; NIST AI RMF, Manage function broadly (subcategory ids not verified in this pass) | **Yes, with a known gap.** `policy/url_policy.py`, `policy/address.py`: scheme allowlist, cloud-metadata block, block/allow lists, private-address block (`safety.block_private_networks`), enforced again at the CDP network layer, canonicalised against every IP spelling. Known limit (spec 8.7): the policy and the browser resolve host names separately, so a DNS answer that changes between the two is not re-checked; sub-resources are not checked unless `enforce_on_subresources` is on | `web-threats.md` |
| 5 | Isolation / sandboxing (per backend) | A compromised agent or page affecting the host or other sessions | Container/VM per session, OS sandbox, `--network none`, code worker process (Anthropic Agent SDK, Claude Code sandboxing, OpenAI Codex); dedicated VM per session, killed and rebuilt after each one (Browserbase) | CSA MAESTRO Layer 4 (Deployment & Infrastructure); MITRE ATLAS (ML Model Access / ML Attack Staging tactics, as the thing isolation defends against) | **Partly, uneven by backend.** `remote_headless`: Chromium's own sandbox stays on where the VM allows (`browser.chromium_sandbox`); the Docker image runs as non-root `pwuser` (`deploy/Dockerfile`); the micro VM itself is named as the real boundary (spec 17.2, not reviewed here) but is not yet built. Code tool runs in a separate process with an empty environment and a memory cap, but spec says plainly "defence in depth, not a boundary" (`code/worker.py`, spec 7.4) and is off by default until a micro VM exists. `takeover_chrome` has no sandbox at all by design: it is the person's real browser. Desktop app: Electron `sandbox: true`, `contextIsolation: true`, `nodeIntegration: false`, permission requests denied by default (`desktop/electron/main.cjs`) | not covered in depth elsewhere; see this report's own section below |
| 6 | Secrets and credentials | Passwords, tokens, cookies, API keys reaching the model or a log | OS keychain, env-only secrets, placeholder substitution at egress, password-manager fill outside model context (Anthropic Managed Agents vaults, 1Password for Claude, Claude Code); Amazon's own Nova Act docs warn developers directly not to feed the agent sensitive information or credentials, because its `evaluate` command can read cookies and the agent may screenshot whatever is on screen | OWASP LLM02:2025 (Sensitive Information Disclosure) | **Partly.** Password field values are shown as dots in the snapshot and never reach the model (spec 8.3, 5.4); the service token and typed text never appear in logs/events/results (spec 4.10, 8.3); `safety.redact_patterns` scrubs matches (`policy/redaction.py`); secrets come only from the environment, never `config.json` or user settings (spec 10.1). No password-manager integration, no credential vault, no scoped per-host secret injection | `prompt-injection.md` (D9); this report |
| 7 | Privacy and personal data (snapshots, screenshots, logs, retention) | PII leaking into model context, logs, or persisting too long | Screenshot opt-in, PII categories never saved to memory, stated retention periods, ZDR option (Anthropic, OpenAI) | OWASP LLM02:2025; NIST AI RMF, Govern and Map functions broadly (subcategory ids not verified in this pass); GDPR/CCPA (legal, not a framework id) | **Partly.** No screenshot unless a call asks for one (spec 5.5); hidden/unrendered text never reaches the model; typed text and field values never reach the event log or viewer (8.3). No stated retention policy for `events.jsonl`/`evals/` on disk, no redaction of PII the agent *does* see (a visible name or address in a snapshot is shown, as 8.3 says, "because that is how it checks its own work"), no consent flow documented | not checked for retention mechanics; this report |
| 8 | Misuse by the user (fraud, spam, harassment, scraping, mass accounts, CAPTCHA solving) | The product being used as an attack or abuse tool | Refusal training, usage-policy enforcement, account bans, CAPTCHA-bypass bans (Anthropic, OpenAI usage policies) | OWASP LLM06:2025 (Excessive Agency); OWASP ASI02 (Tool Misuse) and ASI09 (Human-Agent Trust Exploitation) | **Partly, narrowly.** The engine explicitly never solves a CAPTCHA and never disguises the browser (spec 8.4) — a real anti-misuse control, but a narrow one. No usage-policy enforcement, no refusal layer (the engine does not own a model), no rate limiting of actions, no account-level abuse detection | this report |
| 9 | Financial safety (purchases, transfers, spending caps) | Unwanted or fraudulent spending | Confirm-before-pay, blocked/view-only trading sites, Managed Agents session budgets in dollars; OpenAI's own Operator shipped this and still let an agent buy $31.43 of groceries the user had not approved, which OpenAI acknowledged | OWASP ASI02 (Tool Misuse); OWASP ASI09 (Human-Agent Trust Exploitation) | **Partly.** A control whose name matches `permissions.consequential_words` (`pay, buy, order, purchase, checkout, subscribe, ...`) is always confirmed, every time, on every backend (spec 8.6, 8.8; `tools/toolkit.py` `_consequential`). This is a word-list heuristic, not a transaction-aware check, and there is no spending cap anywhere in the configuration | this report |
| 10 | Irreversible actions and undo | Delete, send, publish with no way back | Deletion protection, critical-path circuit breakers, destructive-action classifiers (Anthropic Cowork, Claude Code auto mode) | NIST AI RMF, Manage function (no specific subcategory id verified in this pass); OWASP ASI08 (Cascading Failures) as the amplifier when an irreversible action is also automated | **Partly.** `delete, remove, transfer` are in the same consequential-word list as financial words, so they are confirmed every time (8.6). No distinct "critical path" concept (e.g. never-undo-able site actions beyond the word list), no undo mechanism, no "earlier steps are not undone" warning beyond the code tool's own result text (spec 7.3 `NOT_UNDONE`) | this report |
| 11 | Identity and impersonation | The agent passing as the person, or as a human, to a site or a person | AI-disclosure requirements, "is being debugged" banners, no-impersonation usage-policy clauses (Anthropic, Chrome extension); IAM-scoped credentials and federated identity for the agent itself (Amazon Nova Act, via AWS IAM and Bedrock AgentCore) | OWASP ASI03 (Identity & Privilege Abuse); usage policies (not a numbered framework); EU AI Act transparency obligation (legal, not reviewed in depth) | **Partly, by design trade-off.** `takeover_chrome` acts with the person's real, signed-in identity on purpose (spec 8.8) — that is the product's point for that backend — but Chrome's own "is being debugged" bar is deliberately left in place as the one tell (spec 8.8, `extension/background.js`). No declared bot/agent user-agent string to sites, no disclosure mechanism for `remote_headless` | this report |
| 12 | Human checks (CAPTCHA, sign-in, 2FA, passkeys) | The agent being pushed to bypass an authentication barrier | Pause-and-hand-to-human, never auto-solve (Anthropic, OpenAI, Claude Code with Chrome) | Usage policies ban CAPTCHA bypass explicitly (Anthropic, OpenAI) | **Yes.** `browser_request_human`; pattern-matched detection of CAPTCHA/sign-in pages (`tools/human_checks.py`); spec 8.4: "The engine never solves a check, never alters the browser's fingerprint and never hides automation." Automatic detection is heuristic (regex on rendered text), not exhaustive | `anthropic-safeguards.md`; `prompt-injection.md` |
| 13 | Human oversight (approval UX, fatigue, kill switch) | A person rubber-stamping dangerous actions, or having no way to stop one | Tiered permission modes, plan approval, global kill key, approval fatigue data (Anthropic 93-97% approve rate, auto mode) | NIST AI RMF, Govern and Manage functions broadly (subcategory ids not verified in this pass) | **Yes, but no classifier layer.** Pause/stop/take-over always one action away (spec 2.3); "confirm" tools raise an approval card with Allow once / Allow on this site / Deny, no answer = deny (8.2); "Ask before: every action" setting (10.2); consequential actions can never use "allow on this site" (8.6). No Anthropic/OpenAI-style classifier that pre-screens actions against the stated task — because the engine does not see the task (open question, `prompt-injection.md` §8.1) | `auto-mode.md`; this report |
| 14 | Resource limits (steps, time, tokens, money) | Runaway loops, denial of wallet, denial of service on the host | Container CPU/memory/pid caps, session spend budgets, step/time ceilings (Anthropic Agent SDK, Managed Agents, Claude Code) | OWASP LLM10:2025 (unbounded consumption) | **Partly.** Code tool: `timeout_s`, `max_steps`, `max_output_chars`, `max_code_chars`, `max_message_chars`, `max_memory_mb` (10.3 `code`); session idle timeout (`browser.timeouts.idle_session_s`); `sessions.max_concurrent`. Reference agent loop: `agent.max_steps`, `agent.max_tokens`. No overall cap for an outside MCP client driving single-tool calls (no step/time/token ceiling on the session itself, only on the code tool and the reference loop), and no money cap at all | this report |
| 15 | Data exfiltration controls | Data read on one site leaving to another, or to an attacker's endpoint | Off-by-default risky tools, upload-directory allowlists, host-scoped secret injection, link-safety checks (Anthropic browser-use tool, OpenAI link safety, Managed Agents vaults) | OWASP LLM02:2025; lethal trifecta (Willison, third party) | **No dedicated check; some side effects of other controls.** `browser_evaluate` and `browser_upload_file` are `confirm` by default (8.2); uploads are restricted to `browser.uploads.allowed_dirs` with symlink/`..` resolution (`policy/files.py`); redaction strips secrets from results (8.3). But nothing checks whether text read from site A is being typed or navigated into site B — the single most-cited gap pattern in `prompt-injection.md` (D10, open question 10) | `prompt-injection.md` |
| 16 | Legal and compliance (robots.txt, site terms, data protection law) | Scraping against terms, breaking site rules, regulatory exposure | User-responsibility clauses, no robots.txt enforcement in any product read | None of the products or frameworks read enforce robots.txt in-band | **No.** No robots.txt check, no terms-of-service awareness, no stated data-protection posture (GDPR/CCPA) anywhere in the spec or code reviewed | this report |
| 17 | Evaluation and red-teaming as an ongoing safeguard | Safeguards decaying or never being tested against a real attacker | System-card eval sections, bug bounties, adaptive-attacker benchmarks (Anthropic, OpenAI, Gray Swan) | MITRE ATLAS (as a technique catalogue to test against) | **Partly.** `bench/` (performance only) and `evals/` (per-task pass/fail records, spec 12.6) are built. `tests/safety/` is named in the project layout (spec 3.2) but does not exist in the repository yet (checked: `tests/` holds `e2e`, `service`, `site`, `support`, `unit`, `viewer`, no `safety`). No adversarial/red-team suite, no published attack-success numbers, because there is no classifier yet to measure | `prompt-injection.md` §7 (benchmark catalogue) |
| 18 | Observability (audit log, replay, alerts) | Not knowing what the agent did, or not being able to show it | Compliance APIs, OpenTelemetry streaming, permission-evaluation events (Anthropic Claude Code, Managed Agents) | NIST AI RMF, Measure function broadly (subcategory ids not verified in this pass); OWASP MCP Security Cheat Sheet's audit-logging guidance (already cited raw in `mcp-security.md`) | **Partly.** `logging.event_log` (`.bap-browser/events.jsonl`), one line per tool call, typed text replaced by length, arguments logged only by name on failure (10.3 `logging`); viewer timeline shows every step live (4.6, 4.8). No alerting, no compliance-API export, no tamper-evidence on the log file, retention of the log file itself is not stated | this report |
| 19 | Supply chain (extension, dependencies, worker process) | A compromised dependency, a tampered extension, a malicious script import | Signed images/SBOMs, verified marketplaces, pinned lockfiles (Docker MCP Toolkit, Anthropic plugin scanning) | OWASP LLM03:2025 (Supply Chain); OWASP ASI04 (Agentic Supply Chain Vulnerabilities) | **Partly.** `uv.lock`/`package-lock.json` pin versions; the code-tool worker imports nothing and runs with `-I -S` (isolated, no site-packages) (`code/runner.py`); the extension is loaded unpacked by hand today (spec 4.9), with no signing or update channel described. No SBOM, no dependency-scanning step named in the spec | this report |
| 20 | Site/domain permission model (take-over Chrome) | The agent acting on sites the person never agreed to, with their real identity | Per-site allow/ask/block, agent-only tab group, consequential actions always re-asked (Anthropic Claude in Chrome permissions) | n/a (product-specific) | **Yes.** Extension-enforced: one tab group for the agent, sites outside it invisible (8.8); per-site `ask`/`allow`/`block` kept in `chrome.storage.local`, re-checked on every `Input.*`/navigate/read command, not trusted to the core's own say (`extension/background.js` `enforce`); consequential actions always ask regardless of site grant | `anthropic-safeguards.md` (for comparison) |
| 21 | Fallback behaviour (timeouts, disconnects, no answer, no viewer) | A session hanging forever, or acting unsupervised when it should not | Deny-on-no-verdict, deny-and-continue, circuit breakers after N denials (Anthropic auto mode, OpenAI auto-review) | n/a | **Yes, thorough for its own states.** No answer within `control.approval_timeout_s` = denied; no viewer connected + confirm tool = denied by default (`control.approval_without_viewer`); bridge disconnect waits `bridge.reconnect_grace_s` then tells the agent plainly (4.5, 4.9); dialog left unanswered is dismissed after `dialogs.timeout_s` (5.7); worker killed and restarted on timeout, `state` loss reported to the agent (7.4). No circuit breaker after N consecutive/total denials the way Claude Code's auto mode has one | `fallbacks.md` (being written) |
| 22 | Settings-based safety ratchet | A person or deployment quietly loosening safety below an organisation's floor | Managed/organisation policy that a project file cannot override (Claude Code) | n/a | **Yes.** Three kinds of settings: free, tighten-only, bridge-kept (10.2); a person can tighten `ask_before`, site lists, upload/download switches but never loosen past the deployment's value; `settings.locked` freezes a setting outright; per-session options can never loosen a safety setting (10.1) | this report |
| 23 | Action-task alignment check | An action that is technically allowed but unrelated to what the person asked, or a "rogue" agent pursuing its own goal | A critic model that sees only the action and the stated goal, never page content (Google Chrome's User Alignment Critic, Anthropic auto mode classifier, OpenAI auto-review); Google's SAIF agent security map names this failure "Rogue Actions" and recommends a second trusted system as a supervisor over the agent's reasoning and plans | OWASP ASI10 (Rogue Agents); Google SAIF agent risk map | **No, and structurally blocked today.** The engine never sees the user's task (it only sees tool calls), so no alignment check is possible without a protocol change — flagged as open question 1 in `prompt-injection.md` | `prompt-injection.md` §8 open question 1 |
| 24 | Browser fingerprinting / automation disclosure | The agent hiding that it is automated, to evade a site's own bot defences | Explicit no-stealth policy (our own spec only; most vendors are silent on this) | Usage policies ban CAPTCHA bypass; none ban stealth directly | **Yes, as policy.** Spec 8.4: never alters the browser's fingerprint, never hides automation. This is a deliberate ethical/legal stance, not just a technical gap | this report |

---

## Categories the other reports do not cover in depth

Ordered by value for cost: cheapest, highest-leverage controls first. Each names the backend(s) it
applies to. `web-threats.md` and `fallbacks.md` were skeletons (headers only) when this was written,
so nothing below assumes their content; `prompt-injection.md` already covers injection-specific
exfiltration and alignment checks in depth, so those are only cross-referenced, not repeated.

### Resource limits (all backends, cheap: configuration only)

Today a step/time/output ceiling exists for the code tool (`code.timeout_s`, `code.max_steps`, …)
and for the reference agent loop (`agent.max_steps`, `agent.max_tokens`), but an outside MCP client
driving single-tool calls over `bap-browser serve` has no session-level ceiling at all: no cap on
calls per session, no wall-clock budget, no cost figure anywhere outside the reference loop's own
price fields. Willison's "default hard budget caps" argument and Anthropic's Managed Agents session
budgets (a dollar figure, paused at the cap, resumable) are both cheap to copy: a
`sessions.max_calls`-style ceiling and a session wall-clock budget, enforced in `Toolkit.call`
beside the existing turn lock, would close this without touching any backend's driver.

### Observability: retention and tamper evidence (all backends, cheap)

`logging.event_log` writes one redacted line per call, which is good, but nothing in the spec states
how long `events.jsonl` or the `evals/` records are kept, and nothing protects the file from being
edited after the fact. NIST AI 600-1 and the MCP security cheat sheet both treat an audit trail a
person can trust as part of the safeguard, not an afterthought. A `logging.retention_days` key plus
either an append-only file mode or a periodic hash of the log (cheap: no external service needed)
would make the existing log load-bearing for an incident review, which it currently is not.

### Irreversible actions: a circuit breaker, not just a word list (all backends, low-medium cost)

Section 8.6's word list (`pay, buy, delete, …`) is a reasonable first pass but, unlike Claude Code's
auto mode, there is no backstop for an action that does not match any word yet destroys something
large (mass-closing tabs, a script that loops a delete across many rows via `browser_run`). Claude
Code's "3 consecutive or 20 total denials pauses the mode" rule and its unconditional protected-path
block are both deterministic, cheap additions: a per-session denial counter that forces every
subsequent action to `confirm` once it is crossed, and a hard ceiling on the code tool's step count
when more than N of its own calls look like repeats of the same tool against a changing argument
(a simple heuristic, not a classifier).

### Financial safety: a spending figure, not only a word match (all backends, low-medium cost)

The consequential-word list catches "buy", "pay", "checkout" in a control's name, but nothing reads
the amount on the page or sums what has already gone through in the session. OpenAI's own Operator
had exactly this gap and let an agent spend $31.43 the person had not approved, which OpenAI
confirmed and fixed by tightening confirmation. A cheap step for us: when a consequential action is
on a control near a currency-formatted number, put that number in the approval summary the person
sees (`"Clicking 'Pay $84.00' on example.com"` instead of `"Clicking 'Pay' on example.com"`), and
optionally refuse without a viewer connected even harder than today for this one class.

### Secrets and credentials: a scoped path for sign-ins (`takeover_chrome`, `bundled_chromium`; medium cost)

The engine never sees a password value today (8.3), which is the right default, but it also has no
first-class way to let a person's own password manager fill a field the way Anthropic's 1Password
integration does ("the password … never enter[s] Claude's context … Access is scoped to the current
task"). Right now the only path for a sign-in is `browser_request_human`, which works but means every
sign-in is a full hand-off. A later, scoped alternative — the extension recognising a password
manager's own fill UI and letting it run without the agent ever being told it happened — would
reduce hand-offs without changing what the model can see.

### Identity and disclosure (`remote_headless`; low cost, policy only)

`takeover_chrome` already carries a tell (Chrome's own "is being debugged" bar, deliberately left in
place, 8.8). `remote_headless` carries none: nothing in the driver sets a distinct user agent or
header that would let a site tell it apart from an ordinary visit. OWASP's ASI03 and the Usage
Policies read for `anthropic-safeguards.md` (no human impersonation; AI disclosure to end users) both
point the same way. This is a policy decision for the product, not a technical one — a custom user
agent string is one line in `browser.user_agent` — so it is flagged here rather than recommended
outright.

### Supply chain: the extension's distribution path (`takeover_chrome`; medium cost)

Today the extension is loaded unpacked, by hand, once (spec 4.9) — fine for development, but it has
no signing, no update channel, and no way for a person to know the copy they loaded is the one the
deployment shipped. The incidents in `mcp-security.md` (Postmark's malicious npm package, Smithery's
path traversal) are the same failure mode: an unverified artifact a person trusted anyway. Before
milestone 2 ships to anyone outside the team, a signed build (Chrome Web Store private listing, or a
checksum published alongside the release) closes this at a cost proportional to the publishing
process already needed for any browser extension.

### Isolation and sandboxing: finishing what the spec already names (`remote_headless`, code tool; medium-high cost)

Section 17.2 names the micro VM as the real boundary, and section 7.4 keeps the code tool off until
one exists — both correct calls. What is not yet described anywhere read in this pass is which of
Anthropic's own hardened-container flags (`--cap-drop ALL`, `--read-only`, `--pids-limit`,
`--memory`, non-root user) the micro VM image will use, beyond the Dockerfile's own non-root `pwuser`
and Chromium's own sandbox. Browserbase's "kill and recreate the VM after every session" pattern is
worth copying directly for `remote_headless`, since bap-browser already discards a fresh profile at
session end (8.1 "Clear browsing data"); the gap is formalising that the VM, not just the browser
profile, is destroyed.

### Legal and compliance posture (`remote_headless`, `takeover_chrome`; low-medium cost, mostly policy)

No product read enforces robots.txt in-band, so bap-browser is not unusual in lacking it, but every
vendor's usage policy (Anthropic, OpenAI) pushes the *user's* responsibility for site terms onto the
product's documentation, not onto the engine. A short, explicit statement in the spec or the
settings screen — "this engine does not check robots.txt or a site's terms; you are responsible for
how you use it" — costs nothing and matches what competitors actually do, rather than leaving the
question unanswered.

### Privacy and PII retention (all backends; low cost)

Section 8.3 is careful about what the model never sees, but says nothing about how long a person's
own data stays in `events.jsonl` or `evals/` once it has been written — a name typed into a form is
never logged, but the fact that a session visited a given site, with its summary line, is. A
`data_dir` retention setting (delete logs and evals older than N days, default on) would bring this
in line with the stated retention periods every vendor in `anthropic-safeguards.md` publishes for
its own products.

---

## Gaps that matter most

Ranked by how much of the attack surface each one closes relative to how little it costs to add,
given that this engine does not own a model and so cannot use the largest category (model training)
at all.

1. **No check on data leaving one site for another.** The single most-cited gap pattern across every
   source read: Willison's "lethal trifecta" and Anthropic's own browser-use tool docs both name it
   directly, and `prompt-injection.md` (D10, open question 10) already flags it as the highest-value
   layer the engine itself can own. *Why it matters most:* it is the one layer that stops a
   successful injection from mattering, independent of whether the injection is caught. *Sources:*
   `prompt-injection.md` D10; Willison, "The lethal trifecta for AI agents"; Anthropic browser-use
   tool security considerations.
2. **No scanner on incoming page content.** Every competitor read (Anthropic, Google, OpenAI,
   Perplexity, Brave) runs at least a classifier or a second model over tool results before the
   agent acts on them; bap-browser declares page content untrusted in words only (spec 8.5). *Why:*
   it is the layer that turns "we told the model not to trust this" into an actual check. *Sources:*
   `prompt-injection.md` D5/D6; `anthropic-safeguards.md` categories 19, 25.
3. **No per-task site scope.** Chrome's Agent Origin Sets and Anthropic's per-site permissions both
   narrow "every site the deployment allows" down to "the sites this task needs"; bap-browser has
   only the former (`safety.allowed_domains`/`blocked_domains`, spec 8.1). *Why:* it shrinks what a
   successful injection or a mistaken action can reach, for free, on every call. *Sources:*
   `prompt-injection.md` D8; Google Chrome "Architecting security for agentic capabilities".
4. **No action-task alignment check, and no way to build one.** The engine never sees the user's
   task, so neither Chrome's User Alignment Critic nor Anthropic's auto-mode classifier pattern can
   exist without a protocol change. *Why it is this high:* it blocks three other gaps on this list
   (financial safety, irreversible-action judgement, and rogue-agent detection) from ever being more
   than a word list. *Sources:* `prompt-injection.md` §8 open question 1; Google SAIF agent risk map
   ("Rogue Actions"); OWASP ASI10.
5. **No spending cap or amount-aware financial check.** The word-list approach (8.6) catches the verb,
   never the number; OpenAI's own Operator shipped confirmation and still let through an unapproved
   $31.43 purchase. *Why:* money is the one harm category every vendor treats as non-negotiable, and
   this engine's current control is the weakest version of what everyone else has. *Sources:* this
   report's financial-safety section; OWASP ASI02/ASI09; Anthropic Managed Agents budgets.
6. **No session-level resource ceiling for outside MCP clients.** Only the code tool and the
   reference loop have limits; a client driving single-tool calls has none. *Why:* unbounded
   consumption is OWASP's own LLM10:2025 and the cheapest gap on this list to close (configuration,
   not architecture). *Sources:* OWASP LLM10:2025; Willison, "default hard budget caps"; Anthropic
   Managed Agents session budgets.
7. **No circuit breaker after repeated denials.** Claude Code's auto mode pauses after 3 consecutive
   or 20 total denials; bap-browser denies each action independently with no session-level memory of
   how many times it has been refused. *Why:* a struggling or misbehaving agent currently just keeps
   trying, each time costing one more approval card for the person. *Sources:* `auto-mode.md` §1.8.
8. **No audit-log retention or tamper-evidence policy.** `events.jsonl` is written but never aged
   out or protected from silent editing. *Why:* an audit log nobody can trust after the fact is not
   much different from no audit log, for the one moment it matters (an incident review). *Sources:*
   this report's observability section; NIST AI 600-1 (Manage function); MCP security cheat sheet.
9. **No signed or updateable distribution for the extension.** Loaded unpacked, by hand, with no way
   for a person to verify they are running the shipped build. *Why:* this is exactly the failure
   pattern behind real incidents (Postmark's malicious npm package, Smithery's path traversal), just
   not yet exploited here because the extension is not yet distributed outside the team. *Sources:*
   `mcp-security.md` §5 (Postmark, Smithery); OWASP LLM03:2025 / ASI04.
10. **No credential-scoped path for sign-ins on `takeover_chrome`/`bundled_chromium`.** The only
    option today is a full hand-off to `browser_request_human`; there is no equivalent to 1Password
    for Claude's "the password never enters the agent's context" pattern. *Why:* it is a usability
    gap today, but becomes a safety gap the moment a deployment is tempted to work around the
    hand-off requirement under time pressure. *Sources:* `anthropic-safeguards.md` category 6 (2f);
    this report's secrets section.
11. **No stated isolation hardening for the micro VM beyond Chromium's own sandbox and a non-root
    container user.** Section 17.2 names the VM as the boundary but the concrete hardening flags
    (`--cap-drop ALL`, `--read-only`, `--pids-limit`, egress-only-through-a-proxy) are not described
    anywhere read. *Why it is not higher:* the VM does not exist yet, so this is a build-it-right
    gap, not an exploitable one today. *Sources:* Anthropic Agent SDK "Securely deploying AI agents";
    Browserbase security docs (VM killed and rebuilt per session).
12. **No declared agent identity for `remote_headless`.** No custom user agent or header distinguishes
    the engine's traffic from an ordinary browser visit, unlike `takeover_chrome`'s debugger bar.
    *Why it is lower:* it is a disclosure/policy question more than an exploitable hole, and the
    product may deliberately want headless traffic to look ordinary. *Sources:* OWASP ASI03; Usage
    Policy no-impersonation clauses (`anthropic-safeguards.md` category 13).
13. **No robots.txt or site-terms posture, stated or enforced.** Consistent with every product read,
    but consistent-with-everyone is not the same as covered. *Why it is not higher:* no competitor
    enforces this either, so it is a documentation gap, not a competitive gap. *Sources:*
    `prompt-injection.md` I-7 (fragment-based evasion is a related, higher-priority issue already
    tracked there); this report's legal-and-compliance section.
14. **No retention policy for the person's own data in logs and evals.** Typed text is correctly
    never logged, but a session's visited sites and summaries persist with no stated lifetime.
    *Why it is not higher:* it is a privacy-hygiene gap, not an attack surface, and is cheap to fix
    whenever it is picked up. *Sources:* this report's privacy section; `anthropic-safeguards.md`
    category 8 (stated retention periods across every product read).
15. **No adversarial or red-team test suite.** `tests/safety/` is named in the project layout but does
    not exist yet, and there is nothing to run it against (no classifier). *Why it is last, not
    absent from the list:* every other gap above should exist before there is anything worth
    red-teaming; building the suite first would test controls that are not there yet. *Sources:*
    `prompt-injection.md` §7 (benchmark catalogue); Nasr et al., "The Attacker Moves Second".

---

## Open questions

1. **Who states the task, and when?** Three gaps on this map (financial amount-awareness, the
   action-task alignment check, and per-task site scoping) all need the engine to know what the
   person or client asked for, which it does not today. This is the same question
   `prompt-injection.md` already raises as its own open question 1; it is repeated here because it
   blocks more of this map than any other single decision.
2. **Where do spending caps and session resource ceilings live** — global configuration, or
   per-system (spec 9.17 already lets several browsers of a window have their own settings)? A
   deployment running several systems may want very different budgets on each.
3. **Does the product want a documented legal/compliance stance before `takeover_chrome` ships to
   anyone outside the team?** That backend acts with the person's real, signed-in identity on live
   sites, which is exactly where a stated robots.txt/terms-of-service position matters most.
4. **Is the extension's unpacked-load workflow (spec 4.9) meant to stay that way past milestone 2?**
   If a wider rollout is planned, the signing/update-channel question in gap 9 needs an answer
   before that rollout, not after.
5. **Which adversarial benchmark, if any, should seed `tests/safety/` once it exists** — our own
   test pages (recommended first, per `prompt-injection.md` §7), BrowseSafe-Bench (licence conflict
   flagged there), WASP (non-commercial licence), or a smaller hand-built set scoped to this map's
   top gaps rather than prompt injection alone?
6. **Was Browser Use's own cloud product findable?** The research for cloud browser vendors turned
   up Browserbase and Steel.dev directly, but a search aimed at "Browser Use" cloud isolation
   returned only generic remote-browser-isolation material, not that vendor's own documentation.
   Row 5 of the map and its isolation section should be treated as missing a direct look at Browser
   Use specifically, not as having ruled it out.

---

## Sources

### Input reports used (read in full or in the sections named)

- `docs/research/anthropic-safeguards.md` — full, including its deduplicated category list (a)
- `docs/research/mcp-security.md` — full, including its server-side checklist (a) and attack table
- `docs/research/prompt-injection.md` — full, including its defence catalogue (D1-D17) and open
  questions
- `docs/research/auto-mode.md` — sections 1 to 3 only, per instructions (Claude Code, Claude in
  Chrome/Cowork, OpenAI); sections past 3 were not read because another report was still writing
  them
- `docs/research/web-threats.md`, `docs/research/fallbacks.md` — checked for structure only (both
  were headers with no body text at the time of writing); not read for content, per instructions

### Our code and spec (checked directly, kind **C**)

- `docs/bap-browser-spec.md` sections 2.3-2.4, 4.5, 4.7-4.10, 5.4-5.8, 7.1-7.4, 8.1-8.8, 10.1-10.3
- `src/bap_browser/policy/url_policy.py`, `policy/address.py`, `policy/files.py`,
  `policy/redaction.py`
- `src/bap_browser/service/app.py`, `service/bridge.py`
- `src/bap_browser/tools/toolkit.py`, `tools/human_checks.py`
- `src/bap_browser/code/worker.py`, `code/runner.py`
- `src/bap_browser/settings/store.py` (partial)
- `src/bap_browser/extension/background.js`
- `desktop/electron/main.cjs`
- `deploy/Dockerfile`
- `tests/` directory listing (to confirm `tests/safety/` does not exist yet)

### Web sources (kind noted; **search** = search-result summary only, not independently fetched;
**fetched** = retrieved and read, through a summarising fetch tool unless stated otherwise)

Google:
- Project Mariner safety/security — search. humansecurity.com/ai-agent/google-mariner/;
  zenity.io/blog/security/a-new-landing-spot-for-ai-agents-the-browser
- Secure AI Framework (SAIF) 2.0 overview — search. safety.google/cybersecurity-advancements/saif;
  saif.google/secure-ai-framework; saif.google/agent-risk-self-assessment
- SAIF agent security map (four components: Application & Perception, Reasoning core,
  Orchestration, Response rendering; "Rogue Actions" and "Sensitive Data Disclosure" as named
  risks; supervisor-agent mitigation) — search, PDF not independently fetched.
  services.google.com/fh/files/misc/googles_approach_for_secure_ai_agents.pdf;
  pymnts.com/cybersecurity/2026/google-devises-battle-plan-to-combat-rogue-ai-agents/

Microsoft:
- Copilot Studio real-time agent security controls (connects to Defender/third-party monitors,
  one-second approve/block window, prompt/response safety, XPIA and jailbreak protections) —
  search. visualstudiomagazine.com/articles/2025/09/08/copilot-studio-adds-near-real-time-security-
  controls-for-ai-agents.aspx
- "Taxonomy of Failure Modes in Agentic AI Systems" v1.0 (April 2025: novel failure modes —
  agent compromise, injection, impersonation, flow manipulation; amplified failure modes — memory
  poisoning, cross-domain prompt injection, human-in-the-loop bypass) and v2.0 (June 2026: seven
  new modes including supply-chain compromise and goal hijacking) — search, not independently
  fetched. microsoft.com/en-us/security/blog/2025/04/24/new-whitepaper-outlines-the-taxonomy-of-
  failure-modes-in-ai-agents; microsoft.com/en-us/security/blog/2026/06/04/updating-taxonomy-
  failure-modes-agentic-ai-systems-year-red-teaming-taught-us

Amazon:
- Nova Act SDK: cloud-isolated execution, AWS IAM credentialing, Amazon Bedrock AgentCore Browser
  Tool, explicit developer warning against feeding the agent sensitive data or credentials because
  `evaluate` can read cookies and the agent may screenshot the screen — search, not independently
  fetched. siliconangle.com/2025/03/31/amazon-introduces-nova-act-ai-agent-can-use-web-browser/;
  aihub.hkuspace.hku.hk (Nova Act SDK preview post); justcall.io/ai-agent-directory/nova-act/

Cloud browser vendors:
- Browserbase: dedicated VM per session, isolated subnet per browser, VM killed and recreated after
  each session, SOC 2 Type II, HIPAA — search. docs.browserbase.com/guides/security;
  docs.browserbase.com/account/enterprise/security
- Steel.dev: open-source, self-hostable browser sandbox behind a REST/WebSocket API; SOC 2 for the
  hosted cloud offering — search. steel.dev/blog/steel-vs-browserbase-a-practical-comparison;
  llms.steel.dev/articles/browserbase-vs-steel/
- "Browser Use" (browser-use.com) specifically was not found by this search; the remote-browser-
  isolation material returned (Cloudflare RBI, Anchor Browser) is generic industry background, not
  that vendor's own documentation. Flagged as open question 6.

OpenAI (supplementing, not duplicating, `auto-mode.md` and `prompt-injection.md`):
- Operator's unapproved $31.43 purchase incident, acknowledged by OpenAI — search, low-confidence
  aggregator source for the incident writeup; treat the dollar figure as reported, not verified by
  this report against OpenAI's own statement. incidentdatabase.ai/es/entities/operator;
  bikes.fan/corpus/gen-908/cross-purposes-live/openai-agent-purchases.html

Frameworks:
- OWASP Top 10 for LLM Applications 2025 (v2.0, published 2024-11-18): LLM01 Prompt Injection,
  LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning, LLM05
  Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector and
  Embedding Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption — search, not
  independently fetched from genai.owasp.org's own page.
- OWASP Top 10 for Agentic Applications (published 2025-12-09): ASI01 Agent Goal Hijack, ASI02 Tool
  Misuse & Exploitation, ASI03 Identity & Privilege Abuse, ASI04 Agentic Supply Chain
  Vulnerabilities, ASI05 Unexpected Code Execution, ASI06 Memory & Context Poisoning, ASI07
  Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI09 Human-Agent Trust
  Exploitation, ASI10 Rogue Agents — fetched directly via a summarising tool.
  genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agent
- OWASP MCP Top 10 (MCP01:2025-MCP10:2025) and the MCP Security Cheat Sheet — not re-fetched here;
  carried over from `mcp-security.md`, which read both raw.
- NIST AI Risk Management Framework: four functions Govern, Map, Measure, Manage — fetched
  directly via a summarising tool. nist.gov/itl/ai-risk-management-framework
- NIST AI 600-1 (Generative AI Profile, published 2024-07-26): maps risks to the four RMF
  functions; said in secondary sources to name 12 risks, but this report could not verify the
  primary document's exact risk list or ids in this pass — treat any specific NIST AI 600-1 risk
  name in this report as unconfirmed. compliance.theartofservice.com and casrai.org pages were
  search snippets only, not read as primary text.
- MITRE ATLAS: 16 tactics, 120 techniques as of release v2026.09 (2026-09-15); inherits 13 tactics
  from MITRE ATT&CK plus two AI-specific tactics, ML Model Access (AML.TA0004) and ML Attack
  Staging (AML.TA0012) — search; the matrix page itself (atlas.mitre.org/matrices/ATLAS) returned
  HTTP 404 when fetched directly in this pass, so tactic/technique names here are from third-party
  summaries (vectra.ai, crowdstrike.com, speakeasy.com), not MITRE's own page.
- CSA MAESTRO: seven-layer threat-modeling framework (1 Foundation Models, 2 Data Operations, 3
  Agent Frameworks, 4 Deployment and Infrastructure, 5 Evaluation and Observability, 6 Security and
  Compliance, 7 Agent Ecosystem) — search, not independently fetched.
  labs.cloudsecurityalliance.org/maestro/; prefactor.tech/blog/maestro-framework-threat-modeling-
  for-ai-agents

All dollar figures, incident details and framework ids above came from secondary or search-summary
sources except where marked "fetched directly"; none were invented, but none should be treated as
verbatim quotes from a primary document unless that report (`anthropic-safeguards.md`,
`mcp-security.md`, `prompt-injection.md`) already verified them raw.
