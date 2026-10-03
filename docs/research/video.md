# "Building verification loops in Claude Code" - content recovery

Research date: 2026-10-03. Source: https://www.youtube.com/watch?v=mQZB0l-rhxE

## 0. Status

- **Transcript obtained: yes.** Route: `uvx yt-dlp --skip-download --write-subs --write-auto-subs` (first route tried, worked).
  - `video.en.vtt` is the **uploader-provided** English caption track (the info JSON lists `subtitles: ['en']`), so it is authoritative, not ASR. `video.en-orig.vtt` is the auto-generated track, kept for reference.
- **On-screen content also recovered.** The spoken track is only 3 minutes and contains almost no numbers, so I downloaded the 1440p video stream to the scratch folder and extracted frames with the locally installed ffmpeg. Every on-screen prompt, the generated `SKILL.md`, and Claude's on-screen output quoted below were read from those frames (`frames/`).
- **Headline finding the caller must know:** the video is a 3:08 concept piece. It does **not** define a "performance system", a budget file, or a checklist. The phrase "performance system" never occurs. The only performance numbers are in the on-screen demo (CLS 0.19 against a 0.1 threshold, fixed to 0.00). "Performance budget" and "accessibility checklist" appear once each, in the closing line, as *examples of things you could codify next*. See section 9 for what this means for the owner's request.

Marking convention below: **[spoken]** = verbatim from the caption file; **[on-screen]** = verbatim text read from video frames; everything else is my paraphrase.

## 1. Metadata

| Field | Value |
| --- | --- |
| Title | Building verification loops in Claude Code |
| Channel | Claude (`@claude`, channel id `UCV03SRZXJEz-hchIAogeJOg`) |
| Upload date | 2026-09-25 |
| Duration | 3:08 (188 s) |
| Speaker | Delba de Oliveira, "Claude Code" (lower-third at 0:00). Single presenter. |
| Views / likes at fetch | 301,339 / 3,686 |
| Chapters | 0:00 Hand off your manual checks; 1:01 Codify your checks; 1:49 The verification loop |
| Description | "Claude Code already runs your tests, type checks, and linters. This video shows how to give it more ways to verify its own work, so it gets further on its own and needs fewer rounds of back and forth." |
| Links in description | https://code.claude.com/docs/en/skills#run-and-verify-your-app and https://code.claude.com/docs/en/best-practices#give-claude-a-way-to-verify-its-work |

A companion blog post by the same author exists (2026-07-22): https://claude.com/blog/building-verification-loops-in-claude-code-with-skills

## 2. Section-by-section summary

### Chapter 1 - Hand off your manual checks (0:00-1:01)

- 0:00-0:08. Claude Code runs a loop per prompt. [spoken] "It gathers context, takes action, verifies its work, and responds." On-screen diagram: `Prompt -> Gather context -> Take action -> Verify results -> Response`, with an arrow from "Verify results" back to "Gather context".
- 0:08-0:19. Today the human is part of the verify step. [spoken] "part of that verify step is you in the browser, clicking around, watching the console, then telling Claude what to fix." On screen: a page at `localhost:5173/journal/slow-brewing-in-kyoto` where a shipping banner pushes content down, with overlay labels [on-screen] "nav.site-nav · layout shift" and "article.post · layout shift", then the user typing [on-screen] "Fix the layout shift on the page".
- 0:19-0:33. Claude already checks against what is in the codebase. [spoken] "It runs your tests, type checks, and linters, and fixes what they catch." [spoken] "But passing all of those doesn't prove the change does what you meant." On-screen graphic "Verifying a change" with four groups: Tests, Type checks, Linters, and a fourth, empty, dotted group labelled "Manual QA".
- 0:33-0:49. What proves the change is the manual check. On-screen two-column table "Manual QA" (label, then description):
  - [on-screen] "Web app - Open the page, click around, watch the console"
  - [on-screen] "Back end - Call an endpoint, read the response"
  - [on-screen] "Mobile app - Tap through the screens in a simulator"
  - [spoken, 0:42] "On a back end, you might call an endpoint and read the response."
- 0:49-1:01. [spoken] "If you codify those steps in your project, Claude can run them itself using tools like a browser, the terminal, and an iOS simulator." [spoken] "When something's wrong, it can fix it and run them again." On-screen iOS example: prompt "Add a quantity stepper to each item on the order screen."; Claude: "Now running the project's verify steps on the simulator." then "The quantity went to 2, but the total still reads $4.50. It is summing the prices without the quantities." then "Fixed. Running the steps again."

### Chapter 2 - Codify your checks (1:01-1:49)

- 1:01-1:15. Start with the bundled verify skill. [spoken] "The first time you use it, it runs your app and checks your change in the app itself. Then it saves the steps that worked as a skill in your project." On screen the user types `/verify`; the tooltip reads [on-screen] "Verify that a code change actually does what it's supposed to by exercising it end-to-end and observing behavior. Bootstraps this repo's project verify skill if none exists yet." Claude runs `npm run dev`, opens the page, interacts with it, and creates `.claude/skills/verify/SKILL.md` (content in section 6). Result line: [on-screen] "Verdict: PASS. The page loads and the change works. I saved the steps that worked to .claude/skills/verify/SKILL.md."
- 1:15-1:37. Extend the generated skill. [spoken] "you should treat the generated skill as a starting point and extend what Claude checks." Her example is layout shift: [spoken] "You can codify that as a performance trace through Google Chrome's DevTools MCP, which measures layout shift as one of the Core Web Vitals." On screen she sends "Add a step: run a performance trace through the Chrome DevTools MCP." and Claude appends step 4 to the skill.
- 1:37-1:49. What a verification skill should state. [spoken] "In this skill, you can say when Claude should run it, what to do when a check fails, and what proves each check passed." [spoken] "The more measurable a check is, the easier it is for Claude to tell whether it's passed or not." On screen she types a second prompt (section 6): run after any UI change; fix and re-run on failure; use a screenshot or score as proof. The resulting file edit is not shown.

### Chapter 3 - The verification loop (1:49-3:08)

- 1:49-2:06. Demo. [spoken] "I will ask Claude to add a Like button to a page I've been working on, which also has some layout shift I haven't yet fixed. Claude will make the edit, and because it's a UI change, it will run the skill on its own." On screen: prompt "Add a Like button to the journal post."; Claude edits 3 files (+75 -5), then prints "Files edited. Now running /verify."
- 2:06-2:14. [spoken] "It starts the dev server, opens the page, clicks the Like button, and takes a screenshot to prove that it works." On screen: a preview card "acme" with the caption "localhost:5173 · Opened in Browser", "Running skill /verify", "Used 6 tools", and a screenshot of the page with the button in its "Liked 13" state.
- 2:14-2:23. [spoken] "Then it runs the performance trace, which finds layout shift. Claude fixes it and runs the checks again, and this time they pass." On screen, in order:
  - "Using chrome-devtools: performance start trace"
  - "CLS is 0.19, over the 0.1 threshold."
  - "Found it. The shipping banner mounts late and pushes the page down." / "Edited 3 files +13 -2"
  - "Re-running the trace on the fixed page." / "Used chrome-devtools: performance start trace"
  - "CLS went from 0.19 to 0.00."
- 2:23-2:35. Result. [spoken] "What I get back is a working Like button, a page that no longer jumps on load, and the screenshots and scores to prove it. Claude runs that verification loop itself without me having to point anything out." Claude's on-screen final message is quoted in full in section 6.
- 2:35-2:47. Why it matters. On-screen slide "When Claude can verify its own work": "It gets further on its own" / "The result is better" / "It takes fewer rounds of back and forth".
- 2:47-3:08. Closing rule. [spoken] "whenever you catch yourself checking something by hand and telling Claude what to fix, ask whether there's something Claude can measure its work against. That could be a performance budget, an accessibility checklist, or your design system's rules. Then codify it, so that the next time it's part of Claude's verification loop." On-screen slide "What to codify next": "A performance budget" / "An accessibility checklist" / "Your design system's rules".

## 3. The verification loop as described

**What it is.** The "verify" stage of Claude Code's per-prompt loop (gather context -> take action -> verify -> respond), extended beyond tests/type checks/linters to include the manual QA a human does afterwards. If verification fails, Claude loops back, fixes, and re-runs the same checks.

**Steps to build it (as shown):**
1. Run the bundled `/verify` once. It launches the app, exercises the change, and records the steps that worked as a project skill at `.claude/skills/verify/SKILL.md`.
2. Treat that file as a starting point. Add the project-specific checks you personally do by hand (her example: layout shift via a performance trace).
3. In the skill, state three things: **when** to run it, **what to do when a check fails**, and **what proves each check passed**.
4. Make each check measurable.
5. From then on Claude runs the skill itself after relevant changes, fixes failures, re-runs, and reports with evidence.

**Feedback tools named or shown:**
- Browser automation: the app's "built-in browser" (on-screen: "Opened in Browser", "Verified in the built-in browser"). Used for opening the page, clicking, reading the console, and taking screenshots.
- Chrome DevTools MCP: `performance start trace`, for Core Web Vitals (CLS in the demo; LCP is also reported).
- Terminal: `npm run dev`.
- iOS Simulator control tool ("Using Claude Code iOS Simulator: control").
- Tests, type checks, linters: named as what Claude already runs.
- **Not mentioned anywhere in the video:** Playwright or Playwright MCP, Lighthouse, hooks, subagents, CLAUDE.md, CI. (Hooks and subagents do appear in the linked written guidance; see section 8.)

**How success criteria are written.** Plain English, numbered steps, in the skill body. The on-screen examples: "Check the console: zero new errors or warnings." and "Click through the change and confirm the new state." Plus an explicit proof requirement: "use a screenshot or score as proof". Guiding principle: [spoken, 1:44] "The more measurable a check is, the easier it is for Claude to tell whether it's passed or not."

**How iteration stops.** When the checks pass on a re-run: [spoken, 2:18] "Claude fixes it and runs the checks again, and this time they pass." The video states no iteration cap, timeout, or escalation rule. Caps exist in the written guidance (section 8), not in the video.

**What the human receives.** The change, plus evidence: [spoken, 2:23] "the screenshots and scores to prove it."

## 4. Performance: everything the video says

**Spoken (complete list):**
- 1:20 layout shift is "where parts of the page jump as content loads."
- 1:28 "You can codify that as a performance trace through Google Chrome's DevTools MCP, which measures layout shift as one of the Core Web Vitals."
- 2:14 "Then it runs the performance trace, which finds layout shift."
- 2:23 "...the screenshots and scores to prove it."
- 2:56 "That could be a performance budget, an accessibility checklist, or your design system's rules."

**On-screen numbers (complete list):**

| Number | Meaning | Where |
| --- | --- | --- |
| CLS 0.19 | Measured Cumulative Layout Shift before the fix | 2:17 |
| 0.1 | The CLS threshold Claude compared against ("over the 0.1 threshold") | 2:17 |
| CLS 0.00 | Measured after the fix | 2:21 |
| 1.2 s | Diagnostic: the banner mounted 1.2 s after load, causing the shift | 2:24 |
| 150px | The fix: space reserved for the banner in the initial HTML | 2:24 |
| "well under 100 ms" | LCP after the fix, reported as not regressed. No LCP threshold is stated | 2:24 |
| 12 -> 13 | Like count, functional proof that the click worked | 2:24 |

**What is absent.** No budget file. No list of thresholds. No LCP/INP/TTFB/bundle-size limits. No Lighthouse score. No "performance system". The one threshold (0.1) is not in the skill text shown on screen; the visible step 4 reads only "Run a performance trace through the Chrome DevTools MCP." The 0.1 figure matches Google's published "good" CLS threshold (section 8), so it most likely came from the tool or the model's knowledge of Core Web Vitals. That attribution is my inference; the skill as updated by the second prompt is never shown.

**How the numbers reach Claude.** The MCP tool returns the trace result into the conversation; Claude reads the metric, compares it with the threshold, and states the comparison ("CLS is 0.19, over the 0.1 threshold."). After the fix it re-runs the same tool and reports before/after ("CLS went from 0.19 to 0.00."). The pattern is: measure -> compare to threshold -> diagnose cause -> fix -> re-measure -> report delta as proof.

## 5. Checklists: everything the video says

- The word "checklist" occurs once: [spoken, 3:00] "an accessibility checklist", as one of three examples of what to codify next. No checklist content is given.
- The closest thing to a checklist actually shown is the numbered step list in `.claude/skills/verify/SKILL.md` (section 6).
- **Where checks live:** a project skill, `.claude/skills/verify/SKILL.md`. The video does not mention CLAUDE.md or hooks as a home for checks.
- **Format:** YAML frontmatter (`name`, `description`) plus numbered plain-English steps.

## 6. Exact on-screen prompts, config and output

Generated skill (1:12), [on-screen], path `.claude/skills/verify/SKILL.md`:

```
---
name: verify
description: Run the Acme Coffee site and check the change in the browser.
---

1. Launch: run `npm run dev` and open http://localhost:5173.
2. Check the console: zero new errors or warnings.
3. Click through the change and confirm the new state.
```

After the first extension prompt (1:39), line 9 is added:

```
4. Run a performance trace through the Chrome DevTools MCP.
```

User prompts, [on-screen]:
- 1:03 `/verify`
- 1:30 "Add a step: run a performance trace through the Chrome DevTools MCP."
- 1:44 "Update the verify skill: 1. run after any UI change 2. fix and re-run on failure 3. use a screenshot or score as proof"
- 1:54 "Add a Like button to the journal post."

Claude's final message in the demo (2:24-2:35), [on-screen]:

> Done. The Like button sits under the headline in index.html:24. Clicking it toggles a liked state, switches the label between "Like" and "Liked", fills the button orange, and bumps the count from 12 to 13 in both the button and the byline.
>
> - The shipping banner caused a layout shift. The verify skill's performance trace flagged CLS 0.19 from the banner mounting after 1.2 s and pushing the nav and article down. I reserved its 150px with a slot in the initial HTML and had banner.js mount into it. CLS is now 0.00 and LCP stayed well under 100 ms.
>
> Verified in the built-in browser with no console errors and screenshots of both states.

Key spoken claims with timestamps:
- 0:29 "But passing all of those doesn't prove the change does what you meant."
- 0:33 "What proves it is the check you do by hand afterwards."
- 0:42 "On a back end, you might call an endpoint and read the response."
- 0:58 "When something's wrong, it can fix it and run them again."
- 1:37 "In this skill, you can say when Claude should run it, what to do when a check fails, and what proves each check passed."
- 1:44 "The more measurable a check is, the easier it is for Claude to tell whether it's passed or not."
- 2:38 "The more Claude can verify its own work, the further it gets on its own."
- 2:47 "...ask whether there's something Claude can measure its work against."

## 7. Design-system and UI/UX verification advice

Minimal. "Your design system's rules" is named at 3:02 as something to codify; no method is given. The UI verification actually demonstrated is: open the page, click the control, confirm the new state, zero new console errors or warnings, screenshot both states, and run a performance trace for layout shift. The companion blog post adds one sentence: Claude Code team members chain "a custom /design skill [that] checks against guidelines in a DESIGN.md file if the change touched UI."

## 8. Corroboration from Anthropic's written guidance

Quotes in this section are exact unless marked otherwise (Claude Code docs were fetched as raw markdown; copies are in `docs/`).

**Best practices - "Give Claude a way to verify its work"** - https://code.claude.com/docs/en/best-practices#give-claude-a-way-to-verify-its-work
- "Claude stops when the work looks done. Without a check it can run, "looks done" is the only signal available, and you become the verification loop"
- "Give Claude something that produces a pass or fail, and the loop closes on its own. Claude does the work, runs the check, reads the result, and iterates until the check passes."
- "The check is anything that returns a signal Claude can read in the conversation: a test suite, a build exit code, a linter, a script that diffs output against a fixture, or a browser screenshot compared against a design."
- Four ways to gate the stop, in increasing strength: in one prompt; a `/goal` condition; "a Stop hook runs your check as a script and blocks the turn from ending until it passes"; "a verification subagent ... has a fresh model try to refute the result, so the agent doing the work isn't the one grading it."
- "Have Claude show evidence rather than asserting success: the test output, the command it ran and what it returned, or a screenshot of the result."
- Failure pattern: "If you can't verify it, don't ship it."

**Skills - "Run and verify your app"** - https://code.claude.com/docs/en/skills#run-and-verify-your-app
- `/verify`: "Build and run your app to confirm a code change does what it should, without falling back to tests or type checks".
- "`/run` and `/verify` work without setup. They infer the launch from your project type (CLI, server, TUI, browser-driven)". So `/verify` is explicitly meant for servers and CLIs, not only web UIs.
- "`/verify` can also record its own recipe ... it writes what worked to `.claude/skills/verify/SKILL.md` at the repo root, or in the touched package directory in a monorepo ... At the repo root, the recorded skill replaces the bundled `/verify`. This requires Claude Code v2.1.200 or later."
- `/run-skill-generator` records how to build and launch the app at `.claude/skills/run-<name>/`.
- "When a session starts with a skill named `verify` or `simplify` in place, Claude Code's commit instructions tell Claude to run it right before each commit, except for changes to docs or tests. This requires Claude Code v2.1.286 or later."
- Tension with the video worth knowing: the docs say bundled skills "including `/verify`, run only when you invoke them". In the video Claude runs it unprompted. The difference is that the video's skill is the *recorded project skill* with an added "run after any UI change" instruction, which Claude can invoke itself.

**Hooks - Stop** - https://code.claude.com/docs/en/hooks#stop
- `decision: "block"` "prevents Claude from stopping"; `reason` "Tells Claude why it should continue".
- Loop protection: "Claude Code applies an 8-consecutive-continuation cap: after stop hooks have continued the turn eight times in a row, Claude Code overrides the next block and ends the turn." Adjustable via `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. Check `stop_hook_active` "to avoid blocking on a condition that will never resolve".

**/goal** - https://code.claude.com/docs/en/goal
- "a separate evaluator ... checks your condition after every turn, so completion is decided by a fresh model rather than the one doing the work."
- The evaluator "doesn't run commands or read files independently, so write the condition as something Claude's own output can demonstrate."
- A good condition has "One measurable end state: a test result, a build exit code, a file count, an empty queue". Bound it with a clause such as "or stop after 20 turns".

**Subagent review** - https://code.claude.com/docs/en/best-practices#add-an-adversarial-review-step
- "Before treating a task as done, have a subagent review the diff in a fresh context and report gaps."
- Caution: "A reviewer prompted to find gaps will usually report some, even when the work is sound".

**Chrome integration** - https://code.claude.com/docs/en/chrome - lists live debugging via console errors, design verification, and web app testing as uses.

**Blog post by the same author** - https://claude.com/blog/building-verification-loops-in-claude-code-with-skills (text extracted from the page HTML, saved as `docs/blog-verification-loops.txt`)
- Definition: "A verification loop is a repeating cycle where an AI agent checks its own work — running tests, linters, or custom checks — and fixes what fails before moving on."
- "A good practice is to list your exact build and test commands in CLAUDE.md so Claude doesn't have to infer them."
- "Pro tip: The check doesn't have to be qualitative to belong here. 'Reject any migration that drops a column without a backfill step' is a deterministic rule no generic linter will catch but a project-specific one will."
- Four placements for a check: standalone (invoked deliberately), embedded (appended to a producing skill), chained (one skill calls the next), on every PR (via GitHub Actions).
- "Chained verification loops can increase token spend, so it's best to test these loops before deploying them broadly."
- Process: "Pick the manual follow-up you did most often this week." -> try `/verify` -> "Write the procedure in plain English, the way you'd hand it to a new teammate on day one." -> make it a skill -> invoke on a new task and confirm the check runs.

**Chrome DevTools MCP tool reference** - https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/tool-reference.md
- `performance_start_trace`: "Start a performance trace on the target webpage. Use to find frontend performance issues, Core Web Vitals (LCP, INP, CLS), and improve page load speed." Also `performance_stop_trace`, `performance_analyze_insight`.
- `lighthouse_audit` exists but "excludes performance. For performance audits, run performance_start_trace".

**Core Web Vitals thresholds** - https://web.dev/articles/vitals (wording as returned by the fetch tool's summariser; re-check before quoting): LCP within 2.5 seconds, INP 200 milliseconds or less, CLS 0.1 or less, assessed at the 75th percentile of page loads. The CLS figure matches the "0.1 threshold" in the video.

## 9. Gaps and cautions for whoever acts on this

1. **"Find the performance system and add their numbers" cannot be satisfied from the video.** The video has no performance system and one threshold (CLS <= 0.1). I do not know which system the owner means. Three readings are plausible and they lead to different work:
   - (a) the Core Web Vitals used in the video. These measure a rendered page (visual stability, paint, interaction), not a backend engine, so their numbers do not transfer.
   - (b) an established backend performance standard to adopt, by analogy with Core Web Vitals. I know of no backend equivalent with universal fixed thresholds; frameworks such as Google SRE's four golden signals name *what* to measure and leave targets to each service's SLOs.
   - (c) a specific reference or competitor system whose measured numbers should become the target, or an existing benchmark harness inside the project.
   Ask the owner which is meant before writing a budget.
2. The video's loop has no stop condition other than "checks pass". An unattended backend loop needs an explicit cap and an escalation rule.
3. The demo metric (CLS) is close to deterministic for a given page. Backend latency is noisy, so a naive "re-run until under budget" loop can pass by luck or chase noise. This is not addressed in the video.
4. The video does not show the skill after the "run after any UI change / fix and re-run / proof" prompt, so the exact wording Anthropic would use for those three clauses is not recoverable.

---

## Translation to backend (my inference)

Everything in this section is my own mapping, not content from the video or the docs. The video's only backend statement is: "On a back end, you might call an endpoint and read the response." I have not inspected the project, so engine-specific items are assumptions to be checked against the real code.

### Element-by-element mapping

| Video element (frontend) | Backend browser-automation engine equivalent |
| --- | --- |
| "Launch: run `npm run dev` and open http://localhost:5173." | Start the engine from a clean state with the recorded launch command, then confirm readiness with a health or handshake call. Take the command from the project's own scripts, never invent it. |
| "Click through the change and confirm the new state." | Drive the real entry point (HTTP endpoint, CLI, SDK or MCP call) through a scripted scenario against a deterministic local fixture page, then assert on both the response and the resulting browser state. |
| "Check the console: zero new errors or warnings." | Zero new ERROR/WARN lines in engine logs, no unhandled rejections or panics, no orphaned browser processes or leaked sessions after the run, clean shutdown with exit code 0. |
| Screenshot "to prove that it works" | A saved evidence bundle: the request/response transcript, structured output diffed against a golden fixture, the relevant log excerpt, and the benchmark result file. Because this engine drives a browser, a screenshot or DOM snapshot of the target page is still a legitimate artefact for scenario checks. |
| Performance trace via Chrome DevTools MCP | A benchmark command that runs fixed scenarios N times and writes machine-readable metrics (JSON) that Claude can read in the conversation. |
| "CLS is 0.19, over the 0.1 threshold." | A comparison step that prints each metric next to its budget and a PASS/FAIL per line, so the failing metric and margin are unambiguous. |
| "CLS went from 0.19 to 0.00." (score as proof) | A before/after table from two benchmark runs on the same machine, included in the final report. |
| "run after any UI change" | Trigger written into the skill description: run after any change to engine runtime code paths, and before each commit. Skip for docs-only changes. |
| "fix and re-run on failure" | Same rule, plus what the video omits: a cap on fix attempts and a stop-and-report path. |
| "A performance budget" | A budget file in the repo (below). |
| "An accessibility checklist" | A reliability and contract checklist (below). |
| "Your design system's rules" | The engine's architecture and API conventions: error shape, timeout and retry policy, logging rules, public API stability. |

### What replaces web performance metrics

Core Web Vitals do not apply to the engine itself. Candidate metric families for a browser-automation backend, grouped by the four golden signals (latency, traffic, errors, saturation; https://sre.google/sre-book/monitoring-distributed-systems/):

- **Latency:** cold start to first ready session; warm session creation; navigation to page-ready; per-action latency (click, type, wait, snapshot, screenshot, extract); end-to-end time for a fixed multi-step task. Report p50 and p95, not means.
- **Traffic / throughput:** actions per second on one session; concurrent sessions sustained on the reference machine.
- **Errors:** scenario success rate over N runs; flake rate; timeout rate; count of new error-level log lines.
- **Saturation / resources:** peak and steady-state memory per session; CPU during idle and during load; process and handle counts after teardown (leak check); output payload size, for example snapshot bytes or tokens returned per action if the engine feeds an LLM.

Which of these matter, and their thresholds, should come from the owner's answer to section 9 item 1 and from a measured baseline. I am deliberately not proposing threshold numbers: I have no source for them and inventing them would violate the brief.

### What the budget file would contain

One entry per metric with: metric id; the exact command and scenario that produces it; unit; statistic (p50, p95, max); sample count and warm-up runs; threshold; allowed noise tolerance; the reference machine and conditions the threshold applies to; the baseline value and the date it was measured; and the source of the threshold (owner-specified target, named reference system, or baseline plus agreed margin). Keep it as data (JSON or YAML) so a script can compare results deterministically and exit non-zero on a breach; that same script can later back a Stop hook or CI job.

### What the checklist would contain

Binary, observable items, each with its proof:
- Engine starts from clean state with the documented command; health check passes. Proof: command output.
- Unit tests, type check, lint and build pass. Proof: exit codes.
- Each end-to-end scenario touching the changed code path returns the expected result. Proof: diff against golden output is empty.
- No new error or warning log lines during the scenarios. Proof: log diff.
- No orphaned browser processes or open sessions after teardown. Proof: process list before and after.
- Failure paths behave as specified: timeouts, navigation errors, invalid input. Proof: the error response captured.
- Every budgeted metric is within budget. Proof: the comparison table.
- Public API unchanged unless the task says otherwise. Proof: contract or snapshot test.

### Where each piece would live

- The procedure: `.claude/skills/verify/SKILL.md`, stating the three things the video asks for (when to run, what to do on failure, what proves each check passed).
- The numbers: a budget file referenced by the skill, not thresholds scattered in prose.
- The launch recipe: recorded via `/run-skill-generator` or written into the skill.
- Exact build/test/bench commands: CLAUDE.md, per the blog post's advice.
- Optional hard gate once the checks are stable: a Stop hook running the comparison script (note the 8-consecutive-continuation cap), or a `/goal` condition with a turn limit for a bounded unattended run.
- Optional independent check: a fresh-context subagent reviewing the diff and the evidence.

### Loop design points the video does not cover

- **Noise:** define sample count, statistic and tolerance in the budget, and require a breach to reproduce before treating it as real. Otherwise "iterate until you reach that level of performance" can end on a lucky run.
- **Stop rule:** stop when all checks pass with evidence, or after a fixed number of failed fix attempts, then report what was tried and what was ruled out.
- **No gaming:** the loop must never pass by loosening a threshold, reducing the scenario, skipping a check, or adding retries and sleeps. Budget changes need the owner's approval.
- **Regression guard:** the video's demo reports an untargeted metric too ("LCP stayed well under 100 ms"). The backend analogue is to report all budgeted metrics on every run, not only the one being optimised.
- **Practical caveat:** the docs place the recorded verify skill "at the repo root". The session environment reported the working directory as not being a git repository, so confirm where a project skill will actually load from.

## 10. Files in this folder

- `video.md` - this document.
- `video.en.vtt` - raw uploader-provided English captions (authoritative transcript). `video.en-en.vtt` is byte-identical.
- `video.en-orig.vtt` - auto-generated captions.
- `video.info.json` - full yt-dlp metadata.
- `video-1440p.webm` - video-only stream used for frame extraction.
- `frames/` - contact sheets (`sheet_01..04.jpg`, one frame per 3 s with timestamps) and higher-resolution frames used to read on-screen text (`a_*`, `b_*`, `f_*`, `g_*`).
- `docs/` - raw copies of the Claude Code docs pages, the blog post, the `/goal` page and the Chrome DevTools MCP tool reference used in section 8.
