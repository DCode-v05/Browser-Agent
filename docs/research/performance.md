# Performance research: published numbers for a browser-automation engine budget

Compiled 2026-10-03. Web research only. No numbers below are my own measurements or extrapolations.

## How to read this file

- **Tag**: `vendor claim` (the party that benefits published it), `independent` (third party with no product in the comparison), `academic` (paper).
- **V** (verification): `F` = I opened the page and the number was on it. `S` = the number came from a search-result summary only (page blocked, not opened, or the opened page did not repeat it). Treat `S` rows as leads, not facts.
- "retrieved" in the Date column means the page carries no date; the value is as of 2026-10-03.
- Where I did a unit conversion or a simple division I say "derived". Nothing else is computed.
- Pages were read through a summarising fetch tool. Before a number goes into the spec as a hard budget, open the source once and confirm it.

---

## 1. Latency of primitives

### 1a. Local browser lifecycle (Playwright / Chromium)

| Metric | Value | What exactly was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Browser launch | 380 ms (median of 10) | `launch` of bundled Chromium, headless | Playwright 1.50.1, Node 20.18, GitHub Actions ubuntu-latest 4 vCPU / 16 GB | 2026-05-18 | independent | F | https://qaskills.sh/blog/cypress-vs-selenium-vs-playwright-performance |
| New context | 12 ms | `newContext` in a running browser | same | 2026-05-18 | independent | F | same |
| Navigation | 45 ms | `goto` to a local Next.js test app | same | 2026-05-18 | independent | F | same |
| Browser close | 28 ms | `close` | same | 2026-05-18 | independent | F | same |
| Full cycle | 465 ms | launch + context + navigate + close | same | 2026-05-18 | independent | F | same |
| Cold launch + small workflow | 476 ms median / 484 ms p95 | launch, navigate, fill form, click delayed control, verify (20 cold runs) | Playwright 1.62.1, Chrome for Testing 149, Apple M5 Pro | post dated 2025 in URL, versions imply a 2026 update; exact date not confirmed | vendor claim (Skyvern blog; neutral on the two libraries compared) | F | https://www.skyvern.com/blog/puppeteer-vs-playwright-complete-performance-comparison-2025/ |
| Same, Puppeteer | 576 ms median / 597 ms p95 | same workflow | Puppeteer 25.8.0 | same | same | F | same |
| New isolated session in a running browser + workflow | 218 ms median / 239 ms p95 (Playwright); 242 / 267 ms (Puppeteer) | new context + page + same workflow (60 runs) | same | same | same | F | same |
| Warm page reuse + workflow | 141 ms median / 149 ms p95 (Playwright); 141 / 151 ms (Puppeteer) | same workflow on an existing page | same | same | same | F | same |
| Headed vs headless | headed about 29.3% slower locally; difference disappears on a VM | Playwright test-suite wall time | not stated | not stated | independent | S | https://dev.to/lucgagan/cross-browser-analysis-of-playwright-testing-efficiency-2ajo |
| Headed Chrome launch (absolute ms) | no published number found | | | | | | |
| Local `connect_over_cdp` time | no published number found | | | | | | |
| New page alone (local) | no published number found | | | | | | |
| Edge / Windows launch times | no published number found | | | | | | |

Context: since Playwright 1.57 headless launches `chrome-headless-shell` and headed launches full Chrome, so headed/headless are two binaries, not one flag (S, https://testdino.com/blog/headed-vs-headless-browser-testing).

### 1b. CLI / daemon overhead in front of the browser

| Metric | Value | What was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Daemon cold start | 1002 ms -> 617 ms (1.6x) | Node daemon vs native Rust daemon | agent-browser v0.20.0 | 2026 (changelog) | vendor claim | F | https://raw.githubusercontent.com/vercel-labs/agent-browser/main/CHANGELOG.md |
| Warm command latency (CLI overhead) | ~150 ms -> ~1 ms | removal of a settle sleep in the CLI path | agent-browser v0.27.2 | 2026 (changelog) | vendor claim | F | same |
| Click latency behind mouse movement | 2471 ms late -> 6 ms | input dispatch queue fix in the stream path | agent-browser v0.33.1 | 2026 (changelog) | vendor claim | F | same |
| End-to-end CLI calls on one page | HTML dump 0.282 s; snapshot 0.304 s; eval 0.316 s; Playwright script with `load` 0.507 s; with `networkidle` 1.506 s | wall time, median of 5 | agent-browser 0.38.1, Playwright 1.59.1, Chrome 153, macOS | 2026-09-17 | independent | F | https://dev.classmethod.jp/en/articles/agent-browser-output-and-time-measured/ |
| Per-command latency table (navigate/snapshot/screenshot/click/fill) for agent-browser | no published number found (benchmark harness exists, results are not in the repo README) | | | | | F | https://raw.githubusercontent.com/vercel-labs/agent-browser/main/benchmarks/README.md |

### 1c. Accessibility snapshot generation

| Metric | Value | What was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| `Accessibility.getFullAXTree`, very large page | 5.3 s | one call on a 35,000-node fixture | Chrome version not stated | 2026-09-17 | independent (GitHub issue, single measurement) | F | https://github.com/openwong2kim/wmux/issues/1371 |
| AX tree first fetch, normal page | under 50 ms for 100-500 AX nodes | "prime" of the AX tree | not stated, methodology not given | not dated | vendor claim (blog) | F | https://modelpiper.com/blog/accessibility-native-testing-ax-selectors |
| AX tree first fetch, large page | 200-500 ms for 10,000+ AX nodes | same | same | not dated | vendor claim (blog) | F | same |
| Snapshot via CLI, small page | 0.304 s | `agent-browser snapshot` wall time (includes CLI round trip) | agent-browser 0.38.1 | 2026-09-17 | independent | F | https://dev.classmethod.jp/en/articles/agent-browser-output-and-time-measured/ |
| Playwright `ariaSnapshot` / `_snapshotForAI` time by page size | no published number found | | | | | | |

Related size limits: Anthropic `read_page` output is capped at 50,000 characters (F, https://platform.claude.com/docs/en/agents-and-tools/tool-use/browser-use-tool); Hermes Agent truncates snapshots at 15,000 characters by default (F, https://hermes-agent.nousresearch.com/docs/user-guide/features/browser).

### 1d. Screenshot capture

| Metric | Value | What was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Screenshot over a cloud browser | median 171 ms (Tilion), 239 ms (Kernel), 245 ms (Browserbase), 299 ms (Browser Use), 412 ms (Hyperbrowser), 761 ms (Notte), 806 ms (Steel) | one screenshot at 1920x1080 on Wikipedia, client in N. Virginia, 100 sessions per provider | provider defaults | 2026-10-02 | independent (site has provider sponsors, incl. Browserbase) | F | https://www.computesdk.com/benchmarks/browsers/browser-throughput |
| Cost of a screenshot to the model loop | about 0.8 s added to LLM inference latency per screenshot | vendor's own agent | Browser Use 1.0 | 2025-10-09 | vendor claim | F | https://browser-use.com/posts/speed-matters |
| Local capture + encode time (PNG vs JPEG) | no published number found | | | | | | |

### 1e. Action overhead (click / type)

| Metric | Value | What was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Actions per second over a cloud browser | 5.97 (Kernel), 5.92 (Tilion), 4.30 (Browserbase), 3.35 (Browser Use), 3.20 (Hyperbrowser), 1.45 (Notte), 1.18 (Steel) | 10 sequential actions per session: navigate, waitForSelector, screenshot, textContent, click, goBack | provider defaults, 1920x1080 | 2026-10-02 | independent (sponsored site) | F | https://www.computesdk.com/benchmarks/browsers/browser-throughput |
| 10-action task duration | median 1.67 s / p95 2.17 s (Kernel) up to median 8.45 s / p95 20.06 s (Steel) | same | same | 2026-10-02 | independent (sponsored site) | F | same |
| `getByRole` vs CSS locator | 677.5 ms vs 497.3 ms for 100 iterations (about 1.5x) | Playwright locator resolution, cited from SerpApi | not stated | not dated | independent (second-hand citation) | F | https://modelpiper.com/blog/accessibility-native-testing-ax-selectors |
| Isolated click or type overhead (actionability checks) | no published number found | | | | | | |

### 1f. CDP screencast

| Metric | Value | What was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Frame rate | 56-60 fps on an animating page | `Page.startScreencast`, 1280x800, JPEG quality 70 | headless Chrome 146 on a Mac | 2026-09-27 | independent (GitHub issue, single measurement) | F | https://github.com/appandflow/stim/issues/1628 |
| Frame size | about 21 KB per frame | same | same | 2026-09-27 | independent | F | same |
| Frame latency | 2 ms p50 from Chrome frame timestamp to receipt (local) | same | same | 2026-09-27 | independent | F | same |
| Input-to-frame latency | about 6 ms from `Input.dispatchMouseEvent` to next frame | same | same | 2026-09-27 | independent | F | same |
| Behaviour | frames are emitted only when the page renders; a static page sends one frame | protocol behaviour | | | independent | S | https://www.browserless.io/blog/puppeteer-screencasts |
| Puppeteer screencast default | 30 fps, WebM/VP9 | recorder default | Puppeteer | retrieved | vendor doc | S | https://pptr.dev/api/puppeteer.page.screencast |
| Remote live-view latency / fps (Browserbase, Steel, Kernel, AgentCore) | no published number found (Kernel says only that its WebRTC view is "much faster than VNC") | | | | | S | https://github.com/kernel/kernel-images |

---

## 2. Session start in cloud browser infrastructure

### 2a. Session lifecycle benchmarks (create + connect + navigate + release)

Five separate benchmarks exist and they disagree strongly. Each row set is one benchmark.

**Steel's own benchmark** (vendor claim, F) - 5,000 runs per provider, client on AWS EC2 us-east-1, 2025-11-07 - https://steel.dev/blog/remote-browser-benchmark

| Provider | Avg total | p95 | Create | Connect | Goto | Release | Success |
|---|---|---|---|---|---|---|---|
| Steel | 894.13 ms (median 867, p99 1,340.05) | 1,090 ms | 181.57 ms | 174.64 ms | 490.29 ms | 47.62 ms | 100% |
| Kernel | 1,518.53 ms | 1,752.10 ms | 261.10 ms (S) | | | 294.57 ms (S) | 100% |
| Browserbase | 1,676.76 ms | 1,873 ms | 188.18 ms (S) | | | 178.99 ms (S) | 99.96% |
| Hyperbrowser | 3,657.11 ms | 5,338 ms | | | | | 100% |
| Anchor | 8,001.29 ms | 11,561 ms | | | | | 97.34% |

**Ritza / techstackups** (independent, F) - 10 measured runs + 3 warm-up, free tiers, client on Hetzner CAX21 in Helsinki (ARM, 4 vCPU, 8 GB), 2026-03-06, updated 2026-05-31 - https://techstackups.com/comparisons/hosted-browser-benchmarks/

| Provider | Total | Create | Connect | Navigate | Release |
|---|---|---|---|---|---|
| Steel | 1,441 ms | 290 | 760 | 209 | 181 |
| Kernel | 1,554 ms | 225 | 815 | 271 | 243 |
| Browserless | 2,090 ms | 0 | 1,665 | 425 | 0 |
| Anchor | 3,730 ms | 1,528 | 1,015 | 315 | 872 |
| Hyperbrowser | 4,012 ms | 1,462 | 1,892 | 496 | 163 |
| Browserbase | 11,933 ms | 9,401 | 1,474 | 648 | 410 |

Same source: second step after a 60 s idle took 248-435 ms; parallel-session overhead ratio 0.34-0.38 where true parallelism was allowed.

**Browserless's own benchmark** (vendor claim, F) - 10 runs, example.com, 2026-01-01 - https://www.browserless.io/blog/hosted-browser-benchmarking

| Provider | Connect avg | Navigation avg | Total avg |
|---|---|---|---|
| Hyperbrowser | 692.5 ms | 251.1 ms | 1,223.6 ms |
| Browserless | 936.4 ms | 166.2 ms | 1,352.6 ms |
| Browserbase | 1,929.9 ms | 317.0 ms | 2,446.9 ms |
| Anchor | 5,582.4 ms | 401.6 ms | 6,484.0 ms |

**Notte "Browser Arena"** (vendor claim, F) - 100 runs per provider, us-east-1 (Notte us-west-2), retrieved 2026-10-03 - https://notte.cc/arena

| Provider | Latency (full lifecycle) | Reliability | Price shown |
|---|---|---|---|
| Kernel | 341 ms | 100% | $0.06/h |
| Notte | 394 ms | 100% | $0.00/h as extracted (elsewhere quoted as $0.05/h) |
| Browserbase | 557 ms | 100% | $0.12/h |
| Steel | 1,190 ms | 100% | $0.10/h |
| Hyperbrowser | 1,761 ms | 99% | $0.10/h |
| Anchor | 3,664 ms | 99% | $0.05/h |
| Browser Use | 4,538 ms | 99% | $0.06/h |

**ComputeSDK lifecycle** (independent, site sponsored by Namespace, Browserbase and others, F) - 100 iterations, client 4 vCPU / 16 GB in N. Virginia, 2026-10-02 - https://www.computesdk.com/benchmarks/browsers/lifecycle

| Provider | Create | Connect | Navigate | Total median | Success |
|---|---|---|---|---|---|
| Tilion | 0.01 s | 0.04 s | 0.06 s | 0.14 s | 100% |
| Kernel | 0.01 s | 0.04 s | 0.15 s | 0.24 s | 93% |
| Browser Use | 0.19 s | 0.18 s | 0.13 s | 0.59 s | 100% |
| Hyperbrowser | 0.25 s | 0.14 s | 0.20 s | 0.70 s | 100% |
| Browserbase | 0.15 s | 0.45 s | 0.18 s | 0.91 s | 100% |
| Steel | 0.74 s | 1.13 s | 0.18 s | 2.71 s | 100% |
| Notte | 1.57 s | 0.49 s | 0.87 s | 3.17 s | 99% |

**Why these are not comparable**: plan tier (Ritza used free tiers; Browserbase's 9.4 s create there versus 0.15-0.19 s elsewhere), client region versus provider region, pre-warmed pools versus on-demand boot, number of runs (10 versus 5,000), and three of the five are run by a competitor that wins its own table. The only stable finding across them: a warm, pooled provider returns a usable session in roughly 0.2-1.7 s end to end, and an un-pooled one takes 3-12 s.

### 2b. Cold start, standby and resume claims

| Provider | Value | What was claimed | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| Kernel (on Unikraft) | under 30 ms to resume a snapshotted browser VM; the 10-40 s full Chrome boot is paid ahead of time | snapshot/restore of a pre-booted microVM | retrieved | vendor claim | S | https://unikraft.com/use-cases/scaling-browser-infrastructure |
| Kernel | "10x faster" cold start, "2x faster" end to end than competitors (no absolute ms); pause/resume up to 72 h; $0 compute while idle | customer story | 2026-01-24 | vendor claim | F | https://unikraft.com/customer-stories/scaling-browser-infrastructure |
| Kernel | standby begins 5 s after the last CDP or live-view activity; billing stops in standby | docs | retrieved | vendor claim | F | https://www.kernel.sh/docs/info/pricing ; https://www.kernel.sh/docs/browsers/standby |
| Kernel | resume-from-standby latency in ms | no published number found in Kernel's own docs | | | F | https://www.kernel.sh/docs/browsers/standby |
| kernel-images (open source) | under 20 ms cold restarts | unikernel image | retrieved | vendor claim | S | https://github.com/kernel/kernel-images |
| Steel | "0.89 s average lifecycle" | headline on pricing page (matches 894 ms above) | retrieved | vendor claim | F | https://steel.dev/pricing |
| Hyperbrowser | "sub-second browser launch"; burst 0 to 5,000 sessions in under 30 s | marketing | retrieved | vendor claim | S | https://ai.notte.cc/answers/browserbase-vs-hyperbrowser (quoting Hyperbrowser) |
| Cloudflare Browser Run | Quick Action response times down "more than 50%" after moving to Containers; no absolute cold-start figure | engineering blog | 2026-05-13 | vendor claim | F | https://blog.cloudflare.com/browser-run-containers |
| Cloudflare | session reuse "eliminates cold-start time"; no number | docs | retrieved | vendor claim | S | https://developers.cloudflare.com/browser-rendering/features/reuse-sessions |
| AWS AgentCore Browser | session start latency | no published number found | | | F | https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-resource-session-management.md |
| Browserbase | session start latency in its own docs | no published number found | | | F | https://docs.browserbase.com/platform/browser/getting-started/manage-browser-session.md |
| Lightpanda | "instant startup"; no number on the cloud product | blog | retrieved | vendor claim | F | https://lightpanda.io/blog/posts/lightpanda-is-a-browser-backend-hermes-agent |
| AWS Lambda + Puppeteer | first launch about 20 s in a cold container, much faster after | community post, older | older (pre-2025) | independent | S | https://dev.to/megabotan/puppeteer-performance-in-aws-lambda-docker-containers-2325 |

### 2c. Limits and price

| Provider | Price per browser-hour | Concurrency | Session length | Other limits | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|---|
| Browserbase | $0.12 (Developer, after 100 h included); $0.10 (Startup, after 500 h) | Free 3, Developer 25, Startup 100, Scale 250+ | max 6 h; Free plan 15 min per session | session creation 5 / 25 / 50 / 150+ per minute; 1-minute minimum billing; CDP connection closed after 10 min without commands; proxy $12 or $10 per GB | retrieved | vendor claim | F | https://www.browserbase.com/pricing ; https://docs.browserbase.com/guides/concurrency-rate-limits ; https://docs.browserbase.com/platform/browser/long-sessions/timeouts.md |
| Steel | $0.10 (Launch); $0.08 (Scale) | 10 / 100 / 1,000+ | 15 min / 1 h / up to 24 h | 60 / 600 requests per minute; proxy $10 or $6 per GB | retrieved | vendor claim | F | https://docs.steel.dev/overview/pricinglimits |
| Kernel | headless $0.0000166667/s (= $0.06/h, derived); headful $0.0001333336/s (= $0.48/h, derived); headful + GPU $0.0008000016/s (= $2.88/h, derived) | Developer 5, Hobbyist 10, Start-Up 150 | max timeout not found in docs | billed only for active runtime; reserved pool capacity counts toward concurrency | retrieved | vendor claim | F | https://www.kernel.sh/docs/info/pricing |
| Anchor | $0.09/h as extracted from the pricing page (Browser Arena lists $0.05/h; conflict not resolved); $0.00-$0.01 per browser creation | Free 5, Starter 25, Team 50, Growth 200, Enterprise 500+ | default max duration 180 min; idle timeout 5 min (S) | proxy $8/GB | retrieved | vendor claim | F / S | https://anchorbrowser.io/pricing ; https://docs.anchorbrowser.io/advanced/session-timeout |
| Hyperbrowser | $0.10 (100 credits at $0.001) | Free 1, Startup ($30/mo) 25, Scale ($100/mo) 100 | not found | billed per second | 2026 (aggregators, "verified June 2026") | vendor claim via third-party listings | S | https://costbench.com/software/browser-automation/hyperbrowser/ ; https://ai.notte.cc/answers/browserbase-vs-hyperbrowser (official pricing page returned no content to the fetch tool) |
| Browser Use Cloud | $0.02 (Browser Arena lists $0.06; conflict not resolved) | by lifetime spend: $0 -> 10, $200 -> 50, $1,000 -> 250, $5,000 -> 500, $25,000 -> 1,000 (API doc page also says "up to 4 concurrent sessions per user"; conflict not resolved) | default 60 min, max 240 min | billed per minute, 1-minute minimum; residential proxy $5/GB | retrieved | vendor claim | F | https://browser-use.com/pricing.md ; https://docs.browser-use.com/cloud/api-v3/browsers/create-browser-session.md |
| Cloudflare Browser Run | $0.09 after 10 h/month included; 10 concurrent included (monthly average of daily peaks), then $2.00 per extra browser | docs page: Free 3, Paid 200 per account. Blog of 2026-05-13: 120 concurrent, up from 30 | browser closes after 60 s of inactivity; up to 10 min with `keep_alive` | docs: new browsers 1 per 20 s (Free), 3 per second (Paid); blog: 60 per minute via Workers binding; Free 10 min/day | retrieved / 2026-05-13 | vendor claim | F | https://developers.cloudflare.com/browser-rendering/platform/limits/ ; https://developers.cloudflare.com/browser-rendering/platform/pricing/ ; https://blog.cloudflare.com/browser-run-containers |
| AWS AgentCore Browser | $0.0895 per vCPU-hour + $0.00945 per GB-hour, charged on consumption | 1,000 concurrent sessions per account (quota page); fundamentals page says up to 500 sessions per browser tool | default 900 s; configurable up to 8 h | fixed 1 vCPU / 4 GB per session; 1 automation stream + 1 live-view stream per session; StartBrowserSession 30 TPS; 10 GB disk; profile max 50 MB | retrieved | vendor claim | F | https://aws.amazon.com/bedrock/agentcore/pricing/ ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html ; https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-resource-session-management.md |
| Lightpanda Cloud | Builder $19/month incl. 300 h, overage $0.08/h; Explorer free with 10 h/month | Explorer 5, Builder 30 | CDP connection closes after 15 min; MCP session after 5 min without a request | metered per second | retrieved | vendor claim | S (prices) / F (timeouts) | https://lightpanda.io/pricing ; https://lightpanda.io/docs/run-on-lightpanda-cloud/limits-and-billing |
| Anthropic Managed Agents (for scale) | $0.08 per session-hour while `running` | | | | retrieved | vendor claim | F | https://platform.claude.com/docs/en/about-claude/pricing |

---

## 3. Tokens and context cost

### 3a. Fixed overhead: tool definitions

| System | Value | What was measured | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| Anthropic `browser_toolset_20260801` | about 6,600 input tokens per request (about 6,610 on Opus 5 / Opus 4.8 / Fable 5, about 6,670 on Sonnet 5); all four optional members add about 880 | default members + tool-use system prompt | released 2026-08; retrieved | vendor claim | F | https://platform.claude.com/docs/en/about-claude/pricing |
| Anthropic `computer_toolset_20260801` | about 4,500 input tokens per request (4,520 / 4,590 on Sonnet 5); disabling `zoom` removes about 410 | same | retrieved | vendor claim | F | same |
| Anthropic earlier computer-use tools (`computer_20250124`, `computer_20251124`) | system prompt overhead 466-499 tokens; tool definition about 735 tokens | per request | retrieved | vendor claim | F | same |
| Anthropic tool-use system prompt | 286 tokens (Opus 5.5, Sonnet 5.5, Opus 5), 354 (Sonnet 5), 497 (Sonnet 4.6), 496 (Haiku 4.5) | added whenever any tool is present, `tool_choice` auto | retrieved | vendor claim | F | same |
| Playwright MCP | about 13.7k tokens (6.8% of a 200k window), 21 tools | Claude Code `/context`; version not stated | not dated | independent | F | https://mintlify.wiki/shanraisshan/claude-code-best-practice/reports/browser-automation-mcp |
| Chrome DevTools MCP | about 19.0k tokens (9.5%), 26 tools | same | not dated | independent | F | same |
| Chrome DevTools MCP | about 17,000 tokens for definitions | not stated | 2026-01-15 | independent | F | https://paddo.dev/blog/agent-browser-context-efficiency/ |
| Claude in Chrome | about 15.4k tokens (7.7%), 16 tools | Claude Code `/context` | not dated | independent | F | https://mintlify.wiki/shanraisshan/claude-code-best-practice/reports/browser-automation-mcp |
| Playwright MCP (2025 baseline) | 5.9k tokens upfront for tool schemas (the extracted text said "48 tool schemas"; the count looks wrong, verify) | Claude Code | 2026-07 | independent | F | https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/ |
| CLI + skill | about 30-50 tokens for a one-line skill description | same | 2026-07 | independent | F | same |

The three Playwright MCP figures (5.9k, 13.7k) differ because of tool count, version and whether deferred tool loading was on. None states a version.

### 3b. Per observation: snapshots

| System | Value | What was measured | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| Playwright MCP full snapshot, Hacker News comment page | about 77,000 tokens (author's leaner tool: about 2,700, minus 96.5%) | tokenizer not stated; author sells the leaner tool | 2026-07-04 (year inferred) | vendor claim | F | https://dev.to/nitai_aharoni_1006318cb51/what-a-browser-mcp-snapshot-actually-costs-i-measured-it-46if |
| Playwright MCP full snapshot, W3C CSS Grid spec | about 169,000 tokens (leaner: about 6,500) | same | same | vendor claim | F | same |
| Same author, 5 live tasks | full snapshots 83 s and about 14 calls; leaner 24 s and about 6 calls | wall time | same | vendor claim | F | same |
| Playwright `_snapshotForAI` on large pages | can exceed 200k tokens | bug report | 2026 | independent | S | https://github.com/openclaw/openclaw/pull/763 |
| "Moderately complex page" snapshot | 10,000-30,000 tokens | general statement, no method | 2026 | independent (blog) | S | https://bug0.com/blog/playwright-cli-vs-playwright-mcp-ai-browser-testing-2026 |
| agent-browser `snapshot -i` | 200-400 tokens per page | interactive elements only; claim repeated by reviewers, not in the project README | 2026-03-27 | independent (repeating vendor framing) | F | https://www.ytyng.com/en/blog/ai-browser-automation-tools-comparison-2026 |
| agent-browser, one Next.js admin page | snapshot 1,806 tokens / 4,193 chars; raw HTML 11,498 tokens / 32,444 chars; targeted `eval` 85 tokens / 328 chars | tiktoken o200k_base, agent-browser 0.38.1 | 2026-09-17 | independent | F | https://dev.classmethod.jp/en/articles/agent-browser-output-and-time-measured/ |
| agent-browser vs Playwright MCP, Hacker News | about 1,200 vs about 14,700 tokens | source page not identified | 2026 | unclear | S | search summary only |
| agent-browser vs Playwright MCP | "93% less context" | no per-page counts, no tokenizer | 2026-01-15 | independent (blog) | F | https://paddo.dev/blog/agent-browser-context-efficiency/ |
| BetterWright | "up to 90%" fewer tokens via semantic snapshots | claim on a marketplace listing; the project README contains no numbers | retrieved | vendor claim | S (claim) / F (README has none) | https://mcpmarket.com/server/better-playwright ; https://raw.githubusercontent.com/BetterWright/betterwright/main/README.md |
| BrowserAct | Amazon product page about 55,000 -> about 2,500 tokens (minus 93% vs raw HTML) | vendor-reported, not replicated | 2026-05-18 | vendor claim | S | https://groundy.com/articles/browseract-open-sources-stealth-browser-engine-with-93-token-reduction-claim/ |
| Playwright MCP docs | no numeric claim (snapshot cost described as "Low - text only") | | retrieved | vendor doc | F | https://playwright.dev/mcp/snapshots |
| Stagehand tokens per `act` / `extract` | no published number found | | | | F | https://browserbase.com/blog/stagehand-v3 |
| browser-use tokens per step | no published number found (model card and speed post give none) | | | | F | https://docs.browser-use.com/open-source/bu-2-0-model-card.md |
| Generic web page as text | 10 kB page about 2,500 tokens; 100 kB about 25,000 | Anthropic web fetch guidance | retrieved | vendor claim | F | https://platform.claude.com/docs/en/about-claude/pricing |

### 3c. Per observation: screenshots

| System | Value | What was measured | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| Anthropic formula | tokens = ceil(width/28) x ceil(height/28) | 28x28-pixel patches | retrieved | vendor claim | F | https://platform.claude.com/docs/en/build-with-claude/vision |
| Anthropic standard tier (models before 4.7) | long edge capped at 1568 px, max 1,568 tokens per image; 1000x1000 = 1,296; 1920x1080 downsized to 1456x819 = 1,560 | | retrieved | vendor claim | F | same |
| Anthropic high-resolution tier (Claude 4.7 and later) | long edge 2576 px, max 4,784 tokens; 1920x1080 = 2,691; 2000x1500 = 3,888; 3840x2160 = 4,784 | | retrieved | vendor claim | F | same |
| Anthropic computer use | each screenshot about 1,000-1,800 input tokens; recommended 1024x768 or 1280x720 (desktop), 1280x800 or 1366x768 (web); keep last 3 screenshots, prune about every 25 turns | docs guidance | retrieved | vendor claim | F | https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool |
| Anthropic many-image rule | more than 20 images in one request triggers a stricter per-image limit (keep each side at or under 2000 px) | counts screenshots in tool results | retrieved | vendor claim | F | https://platform.claude.com/docs/en/build-with-claude/vision |
| OpenAI computer use | about 1,050 tokens per 1024x768 screenshot; about 1,200 at 1280x720; 1920x1080 costs 4-5x more | third-party estimate, not OpenAI | 2026-04-14 | independent | F | https://tokencost.app/blog/gpt-5-4-computer-use-cost |
| OpenAI computer use, context growth | about 15,000 tokens per call by turn 10, about 35,000 by turn 20 | same estimate | 2026-04-14 | independent | F | same |
| OpenAI GPT-5.4 image detail | "original" up to 10.24 M pixels or 6000 px side; "high" up to 2.56 M pixels or 2048 px | announcement, via press | 2026-03-06 | vendor claim | F (secondary) | https://itbrief.co.uk/story/openai-unveils-gpt-5-4-with-advanced-computer-use-tools |

### 3d. Per task

| System | Value | What was measured | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| Playwright MCP vs Playwright CLI | about 114,000 vs about 27,000 tokens (about 4x) | one multi-step task (login flow, cookie dialog, form input; 9-10 steps) in Claude Code. Provenance is disputed: some pages attribute it to a Playwright-team video of February 2026, bug0 attributes it to ytyng.com | 2026-02 / 2026-03-27 | unclear (vendor video or independent blog) | F (secondary pages) | https://www.ytyng.com/en/blog/ai-browser-automation-tools-comparison-2026 ; https://bug0.com/blog/playwright-cli-vs-playwright-mcp-ai-browser-testing-2026 |
| Playwright MCP vs CLI, re-test | MCP session ended at 48k-50k tokens of context; CLI at 45k-48k (no meaningful difference) | same shop task three times in Claude Code; MCP now writes snapshots to disk and defers tool loading | 2026-07 | independent | F | https://www.checklyhq.com/blog/mcp-vs-cli-token-efficiency/ |
| Playwright MCP vs CLI vs agent-browser | MCP about 90 s, 50k tokens, $0.39; CLI about 240 s, 22k tokens, $0.54; agent-browser about 179 s, 24k tokens, $0.39 | about 10-step scenario on the Mozilla homepage; model reported as Claude Sonnet 3.5 (looks stale for April 2026, verify) | 2026-04-03 | independent | F | https://outpost.ranger.net/post/the-hidden-cost-of-fewer-tokens/ |
| Same, second scenario | MCP about 120 s and 60k tokens; CLI about 304 s; agent-browser about 369 s | MCP needed 2-3x fewer tool calls | 2026-04-03 | independent | F | same |
| Vercel internal agent after tool reduction | 37% fewer tokens, 3.5x faster, 42% fewer steps, success 80% -> 100% after removing 80% of tools | Vercel data agent, not a browser agent | 2025-12 | vendor claim | F (secondary) | https://paddo.dev/blog/agent-browser-context-efficiency/ |
| OpenAI GPT-5.4 computer use | 5 turns about 5K input and $0.03; 8 turns about 20K and $0.09; 15 turns about 80K and $0.32; 30 turns about 200K and $0.73 | estimates at 1024x768, medium reasoning | 2026-04-14 | independent | F | https://tokencost.app/blog/gpt-5-4-computer-use-cost |
| OpenAI tool search | 47% fewer tokens on a 250-task benchmark | deferred tool loading, not browser-specific | 2026-03-06 | vendor claim | F (secondary) | https://itbrief.co.uk/story/openai-unveils-gpt-5-4-with-advanced-computer-use-tools |
| Online-Mind2Web judge | about 67,000 tokens per task for WebJudge (GPT-4o) | evaluation cost, not agent cost | 2025-04 | academic | F | https://arxiv.org/html/2504.01382 |

**Comparability warnings**
- Claude 4.7 and later use a tokenizer that produces about 30% more tokens for the same text (F, https://platform.claude.com/docs/en/about-claude/pricing). A token budget must name the tokenizer.
- Most "X% fewer tokens" claims compare a filtered snapshot against a full accessibility tree or raw HTML on one or two pages, with no tokenizer or version stated.
- Fewer tokens did not mean faster: in the Ranger test the lowest-token tools took 2-3x longer.
- The 114k-vs-27k figure predates Playwright MCP's move to file-backed snapshots; Checkly's July 2026 re-test found parity.

---

## 4. Task-level results

### WebVoyager (live sites, 15 websites; published runs use 586-641 tasks after removing stale ones)

| System | Model | Score | Steps / time / cost | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Browser Use | GPT-4o | 89.1% on 586 tasks (55 removed as impossible) | avg steps per site from 8.5 (Coursera) to 36.2 (Google Flights) | 2024-12-15 (older) | vendor claim | F | https://browser-use.com/posts/sota-technical-report |
| OpenAI CUA / Operator | CUA | 87% | | 2025-01 | vendor claim | S (page returned 403) | https://openai.com/index/computer-using-agent/ |
| OpenAI Operator, re-evaluated | Operator | 68.6% (vs 87% claimed); inter-annotator agreement 95.9% | | 2026-03-30 | academic | F | https://arxiv.org/abs/2603.29020 |
| Skyvern 2.0 | GPT-4o + GPT-4o-mini | 85.85% (8 tasks removed); 45% -> 68.7% -> 85.85% across architectures | run on Skyvern Cloud; cost and steps not published | 2025-01-16 | vendor claim | F | https://www.skyvern.com/blog/skyvern-2-0-webvoyager-benchmark-results/ |
| Gemini 2.5 Computer Use | on Browserbase harness, 75-step limit | 79.9% (Claude Sonnet 4 69.4%, OpenAI agent 61.0%) | | 2025-10-07 | vendor claim | S | https://blog.google/technology/google-deepmind/gemini-computer-use-model/ |
| TinyFish / BrowserUse / Smooth / Notte | Claude Sonnet for all | 91.1% / 88.3% / 86.6% / 84.2% on 641 tasks; TinyFish reliability 93.3% | graded by GPT-4o; run by a third party, published by TinyFish | 2026-05 | vendor claim (third-party run) | F | https://www.tinyfish.ai/blog/most-accurate-ai-web-agent |
| Smooth | not stated | 92% | single example: 56 s and $0.05 vs Browser Use 3 min 48 s and $0.20 | not dated | vendor claim | F | https://docs.smooth.sh/performance |
| Magnitude | not verified | 93.9% | | not verified | vendor claim (team-reported) | F (aggregator) | https://leaderboard.steel.dev/leaderboards/webvoyager.md |
| Aggregator top entries | various | 99.19% (browser-control + Fable 5), 98.5% (Alumnium), 97.1% (Surfer 2) | all self- or team-reported | snapshot 2026-03-22 | vendor claims | F | same |

The Online-Mind2Web paper found that 51% of WebVoyager tasks can be solved with a search shortcut, so WebVoyager scores near 90% overstate capability (academic, F, https://arxiv.org/html/2504.01382).

### Online-Mind2Web (300 tasks, 136 live sites)

| System | Model | Score | Steps / time / cost | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| OpenAI Operator | | 61.3% (human eval); easy tasks 83.1% | steps 2.6x the human reference; failed runs use about twice the steps of successful ones | 2025-04 | academic | F | https://arxiv.org/html/2504.01382 |
| Claude Computer Use | 3.7 | 56.3%; easy 90.4% | | 2025-04 | academic | F | same |
| SeeAct / Browser Use / Agent-E | GPT-4o | 30.7% / 30.0% / 28.0% | | 2025-04 | academic | F | same |
| Judge agreement with humans | WebJudge | 83.6% (GPT-4o), 85.7% (o4-mini), 87.0% (WebJudge-7B) | | 2025-04 | academic | F | same |
| SeeAct | GPT-5 Medium | 42.33% | $171.07 for 300 tasks ($0.57 per task, derived) | 2025-08 model; retrieved | independent (Princeton HAL) | F | https://hal.cs.princeton.edu/online_mind2web |
| Browser-Use | Claude Sonnet 4 | 40.00% | $1,577.26 for 300 tasks ($5.26 per task, derived) | retrieved | independent | F | same |
| Browser-Use | Claude 3.7 Sonnet High | 39.33% | $1,151.88 | retrieved | independent | F | same |
| Browser-Use | GPT-4.1 | 36.33% | $236.62 | retrieved | independent | F | same |
| Browser-Use | Gemini 2.0 Flash | 29.00% | $8.83 ($0.03 per task, derived) | retrieved | independent | F | same |
| Gemini 2.5 Computer Use | Browserbase harness, 50-step limit | 65.7% (Claude Sonnet 4 61.0%, OpenAI agent 44.3%); Google's chart: "70%+ accuracy, about 225 s latency" | about 225 s per task | 2025-10-07 | vendor claim | S (scores) / F (latency) | https://blog.google/technology/google-deepmind/gemini-computer-use-model/ |
| Browserbase evaluation campaign | several | scores only in charts | 200+ runs, about 4,000 browser hours, about 3,772 human-verified evals; about 18 browser hours compressed into 20 min by parallelism | 2025-10-07 | vendor claim | F | https://www.browserbase.com/blog/evaluating-browser-agents |
| Browser Use 1.0 | BU 1.0 model | 65.7% | 68 s per task, 3 s per step; vs Gemini 2.5 CU 225 s, Claude Sonnet 4.5 285 s, Claude Sonnet 4 295 s, OpenAI CUA 330 s | 2025-10-09 | vendor claim | F | https://browser-use.com/posts/speed-matters |
| Yutori Navigator | n1 | 78.7% (human eval) | per-step latency 3.3x, 2.7x, 2.0x faster than Claude 4.5, Gemini 2.5 CU, Claude 4.0; n1 averages 3.6 s per step | 2025-11 | vendor claim | F (score, aggregator) / S (latency) | https://leaderboard.steel.dev/leaderboards/online-mind2web ; https://yutori.com/blog/introducing-navigator |
| GPT-5.4 native computer use | GPT-5.4 | 92.8% (screenshot-only observations); ChatGPT Atlas agent mode 70.9% | | 2026-03-06 | vendor claim | F (secondary) | https://itbrief.co.uk/story/openai-unveils-gpt-5-4-with-advanced-computer-use-tools |
| Stagehand | Gemini 2.5 CU / Claude Sonnet 4.5 | 65.0% / 55.0% | | 2026-03 | vendor claim | F (aggregator) | https://leaderboard.steel.dev/leaderboards/online-mind2web |
| Browser Use Cloud | bu-max | 97.0% (custom agentic judge) | | 2026-03 | vendor claim | F (aggregator) | same |

Auto-judged and human-judged rows are not comparable, and neither are different step limits (50 vs unlimited).

### BU Bench V1 (Browser Use's own benchmark, 100 tasks: 20 custom, 20 WebBench, 20 Mind2Web 2, 20 GAIA, 20 BrowseComp)

| Model / agent | Score | Throughput / cost | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| claude-fable-5 | 80.0% | $580.87 per 100-task run; 413 s per task as extracted (verify) | 2026-06-11 | vendor claim | F | https://browser-use.com/posts/ai-browser-agent-benchmark ; https://browser-use.com/posts/what-model-to-use |
| Browser Use Cloud bu-ultra | 78.0% | about 14 tasks per hour | 2026-01-31 | vendor claim | F | same |
| ChatBrowserUse-2 (bu-2-0) on the open-source library | 63.3% | | 2026-01-27 | vendor claim | F | https://docs.browser-use.com/open-source/bu-2-0-model-card.md |
| claude-opus-4-6 | 62.0% | about $100 per run | 2026-01-31 | vendor claim | F | https://browser-use.com/posts/ai-browser-agent-benchmark |
| gemini-3-1-pro / claude-sonnet-4-6 | 59.3% / 59.0% | | 2026-01-31 | vendor claim | F | same |
| gpt-5 | 52.4% | about 6 tasks per hour | 2026-01-31 | vendor claim | F | same |
| gpt-5-mini / gemini-2.5-flash | 37.0% / 35.2% | basic run about $10 | 2026-01-31 | vendor claim | F | same |
| Method | judge gemini-2.5-flash, 87% agreement with 200 hand-labelled traces; one run takes about 3 h | | | | F | same |

An independent write-up notes that 20 of the 100 tasks were written by Browser Use (F, https://agentmarketcap.ai/blog/2026/07/27/browser-use-bu-ultra-throughput-benchmark-conflict).

### WebArena (812 self-hosted tasks) and VisualWebArena

| System | Score | Date | Tag | V | Source |
|---|---|---|---|---|---|
| Human baseline | 78.24% | 2023 | academic | F (aggregator) | https://leaderboard.steel.dev/leaderboards/webarena.md |
| GPT-4 baseline | 14.41% | 2023 (older) | academic | F (aggregator) | same |
| OpenAI CUA / Operator | 58.1% | 2025-01 | vendor claim | S | https://openai.com/index/computer-using-agent/ |
| IBM CUGA | 61.7% | 2025 | vendor claim | F (aggregator) | https://leaderboard.steel.dev/leaderboards/webarena.md |
| Top listed entries | WebTactix (DeepSeek v3.2) 74.3%, OpAgent 71.6%, ColorBrowserAgent 71.2%, Claude Code + GBOX MCP 68.0% | leaderboard updated 2026-06-29 | vendor claims (all self-reported) | F | same |
| GPT-5.4 on WebArena-Verified | 67.3% (DOM + screenshot); GPT-5.2 65.4% | 2026-03-06 | vendor claim | F (secondary) | https://itbrief.co.uk/story/openai-unveils-gpt-5-4-with-advanced-computer-use-tools |
| VisualWebArena human | 88.7% | 2024 (older) | academic | S | https://benchmarklist.com/benchmarks/visualwebarena/ |
| VisualWebArena recent agent scores | no recent published number found (the listing sampled 2026-05-05 still tops out at GPT-4o 19.78%) | | | S | same |

### BrowserGym / WorkArena

| System | Score | Date | Tag | V | Source |
|---|---|---|---|---|---|
| WorkArena L1 top entries | IpaziaHPA + Gemini 3 Flash preview 90.3%; GenericAgent + GPT-5 79.1%; + Claude 4 Sonnet 63.3%; + GPT-5-mini 60.6%; + GPT-4o 45.5% | listing sampled 2026-08-11 | independent (aggregator of the BrowserGym leaderboard) | F | https://benchmarklist.com/benchmarks/workarena_l1/ |
| WorkArena L2 | Claude 3.5 Sonnet 39.1% vs GPT-4o 8.5% | 2024-12 (older) | academic | S | https://arxiv.org/pdf/2412.05467 |
| Observation reduction on WorkArena L1 (33 tasks) | 2.2x faster per step while keeping 84% of the success rate; 3.1x faster on WebLinx keeping 89% | 2026-05-28 | academic | F | https://arxiv.org/abs/2605.29397 |

### REAL Bench

| Item | Value | Date | Tag | V | Source |
|---|---|---|---|---|---|
| Frontier models at launch | at most 41% success | 2025 (NeurIPS 2025) | academic | S | https://nips.cc/virtual/2025/poster/121619 |
| Amazon Nova Act | says it topped the REAL Bench leaderboard; the score itself: no published number found | 2025-12 | vendor claim | S | https://aiwiki.ai/wiki/nova_act |

### OSWorld (desktop; browser-relevant only as a ceiling for screenshot-driven control)

| System | Score | Date | Tag | V | Source |
|---|---|---|---|---|---|
| Human baseline | 72.4% | 2024 | academic | F (secondary) | https://itbrief.co.uk/story/openai-unveils-gpt-5-4-with-advanced-computer-use-tools |
| OpenAI CUA | 38.1% | 2025-01 | vendor claim | S | https://openai.com/index/computer-using-agent/ |
| Claude Sonnet 4.5 | 61.4% | 2025-09 | vendor claim | S | https://pasqualepillitteri.it/en/news/281/claude-sonnet-4-6-benchmarks-features-pricing |
| Claude Sonnet 4.6 / Opus 4.6 | 72.5% / 72.7% | 2026-02 | vendor claim | S | same |
| GPT-5.4 (OSWorld-Verified) | 75.0% (GPT-5.2 47.3%) | 2026-03-06 | vendor claim | F (secondary) | https://itbrief.co.uk/story/openai-unveils-gpt-5-4-with-advanced-computer-use-tools |
| OSWorld-Verified top | Qwen3.8 Max 86.1%; Claude Mythos 5 85%; Claude Fable 5 85%; Claude Opus 4.8 83.4%; Claude Sonnet 5 81.2% | 2026-08-22 | vendor claims (aggregated) | S | https://www.benchlm.ai/benchmarks/osworld-verified |
| OSWorld 2.0 | Claude Opus 5 70.6%; Claude Opus 4.8 20.6% (vs 83.5% on OSWorld-Verified) | 2026 | vendor claims (aggregated) | S | https://www.benchlm.ai/benchmarks/osworld2 |

### Other vendor benchmarks

| System | Value | Date | Tag | V | Source |
|---|---|---|---|---|---|
| Amazon Nova Act | "over 90% task reliability at scale" | 2025-12-02 | vendor claim | F | https://aws.amazon.com/blogs/aws/build-reliable-ai-agents-for-ui-workflow-automation-with-amazon-nova-act-now-generally-available/ |
| Amazon Nova Act (research preview) | ScreenSpot Web Text 0.939, Web Icon 0.879; GroundUI Web 0.805 (Claude 3.7 Sonnet 0.900 / 0.854 / 0.825; OpenAI CUA 0.883 / 0.806 / 0.823) | 2025-03 | vendor claim | S | https://the-decoder.com/nova-act-is-amazons-foray-into-agentic-ai-that-navigates-your-browser/ |
| Lightpanda MCP vs agent-browser + Chromium vs browser-use | AssistantBench strict 66.7% / 57.6% / 39.4%; GAIA Level 1 strict 86.8% / 84.9% / 47.2%; cost per task $1.94 (AssistantBench), $0.34 (GAIA); Claude Sonnet 4.6, 1,800 s timeout | retrieved (2026) | vendor claim | F | https://lightpanda.io/docs/core-concepts/benchmarks |
| Halluminate BrowserBench (296 tasks on anti-bot-protected sites) | Browser Use Cloud 84.8%, Hyperbrowser 76.4%, Anchor 76.0%, Steel 73.3%, Browserbase 70.3% | 2026-03-21 | third-party benchmark published by the winner | F | https://browser-use.com/benchmarks/browsers |
| Hermes Agent browser tool | no published benchmark found (docs only repeat Lightpanda's "9x faster, 16x less memory") | | | F | https://hermes-agent.nousresearch.com/docs/user-guide/features/browser |
| Magnitude: model, date, cost | not verified beyond the aggregator row above | | | | |
| Steps per task and time per task for most agents | no published number found outside Browser Use (2024 per-site steps; 2025 68 s per task) and the Online-Mind2Web paper (Operator 2.6x human steps) | | | | |

### Per-step latency (academic)

| Item | Value | Date | Tag | V | Source |
|---|---|---|---|---|---|
| ReAct-style web agents (WebVoyager, AgentOccam, BrowserUse with GPT-4o) | median 4.7 s LLM inference and 6.6 s browser action time per step; 30-120 s per task; $0.20-0.50 per task | 2026-05-15 | academic | F | https://arxiv.org/html/2605.16565 |
| Share of latency from the web environment | up to 53.7% of total; median web fetch about 6 s; LLM API latency varies up to 69.21x for identical requests; GPT-4o priority tier 9.39 s -> 5.08 s | measured 2025-07 | academic | F | https://arxiv.org/html/2510.16276v1 |

---

## 5. Reliability and resource use

| Metric | Value | What was measured | System / version | Date | Tag | V | Source |
|---|---|---|---|---|---|---|---|
| Chromium headed, idle | 1,094 MB peak | Python driver + all child processes over a 5 s idle period | Playwright (version not stated) | 2025-06-06 | independent | F | https://datawookie.dev/blog/2025/06/playwright-browser-footprint/ |
| Chromium headless, idle | 706 MB; 690 MB with minimal flags | same | same | 2025-06-06 | independent | F | same |
| Firefox / WebKit | 874 / 826 / 770 MB (Firefox headed / headless / minimal); 590 / 588 MB (WebKit) | same | same | 2025-06-06 | independent | F | same |
| Chromium idle / under test load | 142 MB idle; 324 MB peak during a 100-test run | method not detailed, likely browser process only | Playwright 1.50.1 | 2026-05-18 | independent | F | https://qaskills.sh/blog/cypress-vs-selenium-vs-playwright-performance |
| Per tab | 150-300 MB per tab/page | general statement, no method | headless Chromium | not dated | independent (FAQ) | S | https://webscraping.ai/faq/headless-chromium/what-are-the-performance-differences-between-headless-chromium-and-other-browsers |
| New context cost | "KB, not MB" and single-digit ms | general statement | | not dated | independent (blog) | S | https://dev.to/deepak_mishra_35863517037/scaling-headless-browsers-managing-contexts-vs-instances-1d73 |
| Sizing guide | 5-10 concurrent sessions: 2 CPU / 4 GB; 10-20: 4 CPU / 8 GB; 20-50: 8+ CPU / 16+ GB; `--shm-size=2g`; health thresholds at 80% CPU and memory; queue 1.5-2x concurrency | vendor guidance | Browserless Enterprise | retrieved | vendor claim | F | https://docs.browserless.io/enterprise/docker/best-practices |
| Sizing rule of thumb | about 10 concurrent requests per GB | vendor blog | Browserless | 2018-06-04 (old) | vendor claim | F | https://www.browserless.io/blog/observations-running-headless-browser |
| Cloud allocation per session | 1 vCPU / 4 GB fixed | quota | AWS AgentCore Browser | retrieved | vendor claim | F | https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/bedrock-agentcore-limits.html |
| Cloud allocation per session | 8 GB per headful Chromium instance | customer story | Kernel on Unikraft | 2026-01-24 | vendor claim | F | https://unikraft.com/customer-stories/scaling-browser-infrastructure |
| Driver daemon memory | 143 MB (Node) -> 8 MB (Rust); install size 710 MB -> 7 MB | daemon only, excludes Chrome | agent-browser v0.20.0 | 2026 | vendor claim | F | https://raw.githubusercontent.com/vercel-labs/agent-browser/main/CHANGELOG.md |
| Lightpanda vs Chrome, crawl of 933 pages | concurrency 1: 51.68 s / 27.2 MB vs 82.83 s / 1.3 GB; 25: 4.81 s / 123.0 MB vs 46.70 s / 2.0 GB; 100: 5.23 s / 410.2 MB vs 69.37 s / 4.2 GB | wall time and peak memory, AWS m5.xlarge | Chrome 143.0.7499.169 | 2026-01 | vendor claim | F | https://lightpanda.io/docs/core-concepts/benchmarks |
| Lightpanda vs Chrome, single page, 100 cycles | 16 ms vs 185 ms per run; peak memory 21.2 MB vs 402.1 MB; peak CPU 4.6% vs 158.6% | AWS m5.xlarge | Chrome 143.0.7499.109 | 2026-01 | vendor claim | F | same |
| Lightpanda vs Chrome, older headline | 2.3 s vs 25.2 s (11x); 24 MB vs 207 MB (9x) for 100 pages via Puppeteer on m5.large | | | 2025 (older) | vendor claim | S | https://themenonlab.blog/blog/lightpanda-headless-browser-ai-agents |
| Playwright test flake rate | average 0.72%; p90 1.68%, p95 1.91%, p99 2.56% (Cypress 0.83% average) | 60.2 M test records, 285 projects; flaky = unexpected first attempt with a retry | Playwright Test | 2024-06-27 (older) | independent | F | https://currents.dev/posts/cypress-vs-playwright-flakiness-comparison |
| Flake causes | 46.5% of flaky tests are resource-dependent (CPU, memory, I/O) | 52 projects | | not verified | academic (cited second-hand) | S | https://testdino.com/blog/flaky-test-benchmark-report-2026 |
| Cloud session success rate | 97.34% (Anchor), 99.96% (Browserbase), 100% (Steel, Kernel, Hyperbrowser) over 5,000 lifecycles | create/connect/goto/release | | 2025-11-07 | vendor claim | F | https://steel.dev/blog/remote-browser-benchmark |
| Cloud session success rate | 93% (Kernel), 99% (Notte), 100% (others) over 100 lifecycles | same shape | | 2026-10-02 | independent (sponsored site) | F | https://www.computesdk.com/benchmarks/browsers/lifecycle |
| Agent run completion without crash or timeout | 93.3% (TinyFish); failure split by infrastructure vs reasoning: TinyFish 75/25, BrowserUse 4/88, Smooth 26/72, Notte 79/21 | WebVoyager, 641 tasks | | 2026-05 | vendor claim | F | https://www.tinyfish.ai/blog/most-accurate-ai-web-agent |
| Browser crash rate per session or per hour | no published number found | | | | | | |
| CPU per idle or active session (Chrome) | no published number found, except the Lightpanda comparison above | | | | | | |

Not comparable: the 706 MB and 142 MB "idle Chromium" figures differ because one includes the Python driver and every child process and the other does not say what it includes.

---

## 6. Speed-focused agent claims

| System | Value | What was measured | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| Browser Use 1.0 | 68 s average per task, about 3 s per step; a GitHub PR-search example 15 s vs 75 s for Gemini 2.5 CU | Online-Mind2Web, own harness | 2025-10-09 | vendor claim | F | https://browser-use.com/posts/speed-matters |
| Browser Use LLM gateway | "20 steps per minute"; latency "6x" lower than computer-use models; LLM inference about 68 s per trajectory vs 225-330 s | LLM inference time only | 2025-10-08 | vendor claim | F | https://browser-use.com/posts/llm-gateway |
| Browser Use, technique notes | output tokens cost about 215x more time than input tokens, so actions are kept to 10-15 output tokens; screenshots only when needed | own measurements | 2025-10-09 | vendor claim | F | https://browser-use.com/posts/speed-matters |
| Browser Use custom models | about 40% fewer steps than GPT-4o on internal tasks; "Skill" replays at $0.02 per execution with no per-step LLM cost | changelog summary | 2026-03 | vendor claim | S | https://aitoolsatlas.ai/tools/browser-use/changelog |
| Browser Use move from Playwright to raw CDP | no numbers; removes "a 2nd network hop" through the Node Playwright server | | 2025-08-20 | vendor claim | F | https://browser-use.com/posts/playwright-to-cdp |
| Anchor + Groq | 28 actions per minute | `openai/gpt-oss-120b` on Groq, pool of 10 pre-warmed Chrome sessions, parsed DOM, action batching | 2025-08-19 | vendor claim | F | https://anchorbrowser.io/blog/how-we-solved-high-speed-browser-agents-anchor-x-groq |
| Yutori n1 / Navigator | 3.6 s average per step; 2.2x faster than Claude 4.5 Opus, 1.7x faster than Gemini 2.5 CU | own evaluation | 2025-11 to 2026 | vendor claim | S | https://yutori.com/blog/introducing-n1 |
| Stagehand v3 (CDP-native) | 44.11% faster on average than v2 on deeply nested iframe and shadow-DOM interactions | own benchmark, detail in an external document | 2025-10-29 | vendor claim | F | https://browserbase.com/blog/stagehand-v3 |
| Stagehand server-side cache | "as high as about 80%" speed-up on the second of two identical sequential runs; cache entries live 48 h; "varies heavily by workload" | first run writes the cache, second replays without an LLM call | 2026-02-24 | vendor claim | F | https://browserbase.com/blog/stagehand-caching |
| Stagehand caching | "up to 2x faster" and "about 30% cost reduction" on repeat workflows | source page not identified | 2026 | vendor claim | S | search summary only |
| Stagehand cache behaviour | cached `act()` replays with self-healing off; falls back to full inference if the selector no longer resolves; no numbers | docs | retrieved | vendor doc | F | https://docs.stagehand.dev/v4/best-practices/caching |
| Skyvern code caching ("explore, then replay") | average run 278.95 s -> 119.92 s (2.3x); average cost $0.11 -> $0.04 (2.7x); falls back to the agent when cached code fails | "across customers"; run count not stated | 2025-10-17, updated 2026-08-24 | vendor claim | F | https://www.skyvern.com/blog/asking-ai-to-build-scrapers-should-be-easy-right/ |
| Skim (speculative execution) | 33.4% lower latency and 1.9x lower median per-task cost with no accuracy loss; 12.6-45.3% of tasks finish on the fast path | WebVoyager and WebShop with three agent backbones | 2026-05-15 | academic | F | https://arxiv.org/abs/2605.16565 |
| SpecCache | up to 3.2x lower web-environment latency; cache hit rate 83.3% vs 8.9% random (WebWalkerQA) | 15 models, 5 providers | 2025-10 | academic | F | https://arxiv.org/html/2510.16276v1 |
| Leaner snapshots | 83 s -> 24 s (3.5x) and about 14 -> 6 calls on 5 live tasks | author's own tool vs Playwright MCP full snapshots | 2026-07 | vendor claim | F | https://dev.to/nitai_aharoni_1006318cb51/what-a-browser-mcp-snapshot-actually-costs-i-measured-it-46if |
| Parallelism | about 18 browser hours of evaluation finished in 20 minutes | Browserbase evaluation runs | 2025-10-07 | vendor claim | F | https://www.browserbase.com/blog/evaluating-browser-agents |
| Cache hit rate in production for any replay system | no published number found | | | | | | |
| Replay failure / fallback rate | no published number found | | | | | | |

---

## 7. Frontend analogy: how web performance budgets are written

| Item | Value | Notes | Date | Tag | V | Source |
|---|---|---|---|---|---|---|
| LCP | good at or under 2.5 s; needs improvement 2.5-4 s; poor over 4 s | loading | updated 2024-10-31 | vendor standard (Google) | F | https://web.dev/articles/vitals |
| INP | good at or under 200 ms; needs improvement 200-500 ms; poor over 500 ms | interactivity | same | same | F | same |
| CLS | good at or under 0.1; needs improvement 0.1-0.25; poor over 0.25 | visual stability | same | same | F | same |
| Pass rule | measured at the 75th percentile of page loads, split by mobile and desktop; all three must pass | field data, not lab | same | same | F | same |
| Supporting metrics | TTFB, FCP, TBT (TBT is the lab proxy for INP) | diagnostics, not pass/fail | same | same | F | same |
| Definition of a budget | "a set of limits imposed on metrics that affect site performance" | three kinds: quantity-based (bytes, request counts), milestone timings (FCP, TTI), rule-based (Lighthouse score) | 2018-11-05 | vendor standard | F | https://web.dev/articles/performance-budgets-101 |
| Example budget lines | under 170 KB JavaScript on mobile; under 2 MB images on desktop; load in under 5 s on slow 3G; Lighthouse score over 80 | one line = scope + metric + limit + condition | 2018-11-05 | vendor standard | F | same |
| Lighthouse `budget.json` (LightWallet) | array of objects keyed by `path`; `timings` in ms (example: interactive 3000, first-meaningful-paint 1000); `resourceSizes` in KB (script 125, total 300); `resourceCounts` (third-party 10) | run with `lighthouse <url> --budget-path=./budget.json`; report shows a Budgets section with the overage | 2019-06 | vendor standard | F | https://web.dev/articles/use-lighthouse-for-performance-budgets |
| Lighthouse CI assertions | per-audit rules with a level (`error` fails the build, `warn` logs, `off`) and either `maxNumericValue` (for example LCP 2500) or `minScore` (for example performance 0.9) | failure output prints expected vs found | retrieved | independent (guide to the tool) | S | https://unlighthouse.dev/learn-lighthouse/lighthouse-ci/budgets |

What carries over to a backend budget: (1) three bands per metric, not one number; (2) a named percentile (p75) over real runs, plus a separate lab number; (3) every line states scope, metric, unit, limit and the condition it was measured under; (4) two severities, warn and error, enforced in CI; (5) quantity budgets (bytes, counts) sit next to timing budgets, which maps directly onto tokens per snapshot next to milliseconds per action.

---

## Suggested budget lines

"Best" and "typical" are published figures only. "Missing" means measure it yourself before fixing a limit. Nothing here is a recommendation of a specific limit; the owner sets those.

| # | Metric | Best published figure | Typical published figure | Missing / caveat |
|---|---|---|---|---|
| 1 | Local headless Chromium launch | 380 ms (Playwright 1.50.1, 4 vCPU Linux CI) | 380-480 ms launch; 465-476 ms for launch + first navigation | headed Chrome, Edge, Windows: no published number. Headed is "about 29% slower" locally (one source) |
| 2 | New context | 12 ms | 12 ms alone; 218 ms median / 239 ms p95 for context + page + small workflow | new page alone: none |
| 3 | Warm page: small workflow | 141 ms median / 149 ms p95 | same | one machine (Apple M5 Pro), one fixture |
| 4 | CDP connect, local | none | none | no published number found |
| 5 | CDP connect, cloud | 40 ms (ComputeSDK, Kernel and Tilion) | 175-815 ms; up to 1.9 s | depends on client region and TLS; benchmarks disagree |
| 6 | Navigation overhead | 45 ms (local app) | 130-650 ms to example.com or Wikipedia over a cloud browser | no figure isolates engine overhead from network |
| 7 | Accessibility snapshot, small page | under 50 ms for 100-500 AX nodes (unverified method) | about 0.3 s end to end through a CLI | no Playwright `ariaSnapshot` timing published |
| 8 | Accessibility snapshot, very large page | 200-500 ms for 10,000+ AX nodes (unverified method) | 5.3 s for `getFullAXTree` on 35,000 nodes (single measurement) | only two data points, neither rigorous |
| 9 | Screenshot capture | 171 ms median (remote, 1920x1080) | 240-410 ms remote; 760-810 ms on the slowest providers | local capture and PNG-vs-JPEG encode time: none |
| 10 | Action overhead | about 1 ms CLI overhead (agent-browser warm path); 5.97 mixed actions per second remote | 3-6 mixed actions per second remote | isolated click and type overhead: none |
| 11 | Screencast | 56-60 fps, about 21 KB per frame, 2 ms p50, about 6 ms input-to-frame (local, 1280 px, JPEG q70) | 30 fps recorder default | one anecdotal measurement; remote live-view latency: none |
| 12 | Cloud session ready (create + connect + first navigation) | 0.14-0.34 s | 0.6-1.7 s | 3-12 s on un-pooled or free-tier paths; five benchmarks, three run by vendors |
| 13 | Cloud session create only | about 10 ms (pooled) to 150-290 ms | 150-300 ms | 1.5-9.4 s observed on free tiers |
| 14 | Resume from standby | under 30 ms (Kernel on Unikraft, vendor, search summary only) | none | no independent figure; Kernel's own docs give no ms |
| 15 | Price per browser-hour | $0.02 (Browser Use Cloud) | $0.06-$0.12 | headful $0.48/h and GPU $2.88/h at Kernel; AgentCore bills per vCPU-hour and GB-hour |
| 16 | Concurrency ceilings | 1,000+ (Steel Enterprise, AgentCore default quota, Browser Use top tier) | 25-250 on self-serve paid plans | creation-rate limits (25-150 per minute at Browserbase) bind before concurrency |
| 17 | Max session length | 24 h (Steel Enterprise) | 4-8 h (Browser Use 4 h, Browserbase 6 h, AgentCore 8 h) | Cloudflare closes a browser after 60 s idle (10 min with `keep_alive`); Lightpanda Cloud closes a CDP connection after 15 min; Steel Launch plan 15 min |
| 18 | Tool-definition overhead | 30-50 tokens (CLI + skill line) | 4,500 (Anthropic computer toolset), 6,600 (Anthropic browser toolset), 13.7k (Playwright MCP), 17-19k (Chrome DevTools MCP) | MCP figures carry no version; deferred tool loading changes them |
| 19 | Tokens per snapshot | 200-400 (agent-browser interactive-only, claimed); 85 for a targeted eval (measured) | 1,800 measured on a simple page; 10-30k claimed for a moderately complex page | worst case 77k-169k and over 200k on huge pages; no tokenizer stated in most sources |
| 20 | Tokens per screenshot | 1,296 at 1000x1000 (Anthropic); about 1,050 at 1024x768 (OpenAI, third-party estimate) | 1,000-1,800 (Anthropic computer-use guidance); 1,560 for 1920x1080 on standard tier | 2,691 for 1920x1080 and up to 4,784 on Claude 4.7+ high-resolution tier |
| 21 | Tokens per 10-step task | 22-27k (Playwright CLI, agent-browser) | 45-60k (Playwright MCP in April-July 2026; CLI 45-48k in the July re-test) | 114k is an early-2026 MCP figure; low tokens took 2-3x longer in one test |
| 22 | Time per step | about 3 s (Browser Use 1.0); 3.6 s (Yutori n1); 28 actions per minute (Anchor + Groq) | 4.7 s LLM + 6.6 s browser per step (academic median) | vendor numbers exclude or minimise browser time |
| 23 | Time per task | 68 s (Browser Use 1.0, Online-Mind2Web) | 225-330 s for computer-use models on the same harness; 30-120 s for ReAct agents on WebVoyager | no independent time-per-task leaderboard |
| 24 | Cost per task | $0.03 (Browser-Use + Gemini 2.0 Flash, HAL, derived) | $0.20-0.50 (academic); $0.57 (SeeAct + GPT-5, derived) | $5.26-5.81 with frontier Claude models |
| 25 | Success, Online-Mind2Web | 97.0% (Browser Use Cloud, custom judge), 92.8% (GPT-5.4) | 55-79% vendor-reported in 2025-2026; 40-42% on the independent HAL board | judges and step limits differ; auto judges agree with humans about 85% |
| 26 | Success, WebVoyager | 91-99% self-reported | 85-89% | independent re-test put Operator at 68.6% vs 87% claimed |
| 27 | Success, WebArena | 74.3% self-reported | 58-68% | human 78.24% |
| 28 | Memory per browser | 142 MB idle (browser only, method unclear) | 690-706 MB headless and 1,094 MB headed including driver and child processes; 300-500 MB per session as a sizing rule | 4 GB (AgentCore) and 8 GB (Kernel headful) allocated per cloud session |
| 29 | Sessions per host | about 10 per GB (2018 rule of thumb) | 5-10 sessions per 2 CPU / 4 GB | no recent independent density study |
| 30 | Flake rate | 0.72% average for Playwright tests (2024) | p95 1.91%, p99 2.56% | browser crash rate per session: no published number found |
| 31 | Cloud session success | 100% | 99-100% | 93% and 97.34% observed for single providers |
| 32 | Replay speed-up | about 80% faster second run (Stagehand cache) | 2.3x faster and 2.7x cheaper (Skyvern); 33.4% latency cut (Skim, academic) | cache hit rate and fallback rate in production: none |

### Biggest gaps (nothing published)

1. Local primitives on Windows, with headed Chrome, and with Edge.
2. `connect_over_cdp` latency and per-action overhead (click, type) in isolation.
3. Accessibility-snapshot time as a function of page size for Playwright's own snapshot.
4. Local screenshot capture and encode time by format.
5. Remote live-view / screencast latency for any cloud provider.
6. Browser crash rate per session-hour.
7. Tokens per step for browser-use and Stagehand.
8. Independent time-per-task and steps-per-task data across agents.
9. Cache hit and fallback rates for replay systems.
