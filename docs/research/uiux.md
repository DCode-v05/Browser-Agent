# UI/UX of shipping browser-agent products: research findings

Research date: 2026-10-03. Scope: how shipping (and recently discontinued) products design the surfaces of a "give an agent a task, watch it drive a browser, approve, take over, review" app.

## 0. How to read this

**Evidence marks**

- No mark: read directly on the vendor's own page (docs, help centre, blog).
- `[excerpt]`: vendor page that refused a direct fetch (HTTP 403); the claim comes from search-engine excerpts of that page. Treat as likely but not line-checked.
- `[press]`: only third-party coverage (reviews, blogs, news) supports it.
- `[unverified]`: I am not sure it is right, or the only source is weak or second-hand.
- "Not found" means I looked and found no evidence. It does not mean the product lacks the feature.

**Caveat on quotes.** Every page was read through an automated reader that summarises. Strings in quotation marks are what that reader returned as exact text. Check them against the live product before copying microcopy into the spec. Two known conflicts are flagged, in sections 1.1 and 1.7.

**Source IDs** (for example `[A1]`) resolve to URLs in section 9.

### Product status on 2026-10-03

| Product | Status | Source |
|---|---|---|
| Claude in Chrome | Active. Side panel now runs as a Cowork session; "classic" side panel still selectable | [A2] |
| Claude Cowork built-in browser (Claude Desktop) | Active, launched week of 2026-08-26 | [A8] |
| Claude computer use (Cowork) | Active | [A10] |
| OpenAI Operator | Discontinued. Deprecated 2025-08-01, shut down 2025-08-31, folded into ChatGPT agent | [O20] |
| ChatGPT agent | Removed early August 2026. Help centre: "ChatGPT agent is no longer available. Use ChatGPT Work..." | [O4], [O21] `[press]` |
| ChatGPT Atlas | Shut down 2026-08-09 (macOS only for its whole life) | [O17] |
| ChatGPT Work cloud browser | Active | [O5], [O6] |
| ChatGPT desktop built-in browser (`@Browser`) and browser extension (`@Chrome`) | Active | [O5], [O11] |
| Perplexity Comet (+ Background Assistant) | Active | [P1] `[press]` |
| Chrome auto browse (Gemini in Chrome) | Active, US, paid tiers, daily caps | [G1] |
| Project Mariner | Shut down 2026-05-04; technology folded into Gemini Agent and Chrome auto browse | [G8] `[press]` |
| Edge "Browse with Copilot" (was Copilot Actions / Copilot Mode) | Active; Edge for Business agentic browsing in limited preview since 2026-05-20 | [M1], [M2] |
| Opera Neon | Active | [N1] |
| Manus (cloud browser, Browser Operator) | Active | [U1], [U2] |
| Browserbase, Browser Use Cloud, Steel, Skyvern | Active | sections 1.13 to 1.16 |
| Amazon Nova Act HITL, AWS AgentCore Browser, Cloudflare Browser Run | Active | sections 1.17 to 1.19 |
| Hermes Agent, OpenClaw | Active (open source) | sections 1.20, 1.21 |

---

## 1. Per-product findings

Dimension numbers follow the brief: 1 layout, 2 agent presence, 3 timeline, 4 controls, 5 approvals, 6 human handoff, 7 credentials, 8 tabs and multi-session, 9 result and review, 10 settings and policy, 11 error and blocked states, 12 accessibility and motion.

### 1.1 Claude in Chrome (Anthropic)

Sources: [A1] [A2] [A3] [A4] [A5] [A6] [A12]

- **1 Layout.** A Chrome side panel that "stays visible while you browse", opened from the toolbar icon. On paid plans the panel hosts a full Cowork session; a three-dot menu offers "Switch back to classic" [A2] [A5].
- **2 Presence.** Tabs Claude opens go into "a separate group with a different color, so you can easily tell which tabs Claude is using versus your personal browsing" [A2]. On the page itself an animated glow border is injected while the agent uses the tab: class `.claude-agent-glow-border`, animation `claude-pulse`, built from layered inset box-shadows [A6] (a user bug report, not vendor documentation).
- **4 Controls.** Clock icon (upper right) schedules tasks: daily, weekly, monthly or annually. A record icon (classic panel only) records the user's own steps and saves them as a shortcut. Typing "/" lists saved shortcuts [A2]. The safety article tells users to "stop the task immediately" on odd behaviour but does not name the control [A3].
- **5 Approvals.** A drop-down on the chat input selects one of three modes: "Manually approve (Manual)" (formerly "Ask before acting"), "Automatically approve (Auto)" (default: Claude reviews each action for safety, blocks unsafe ones, pauses when needed) and "Skip all approvals (Skip)" [A1]. In Manual each action gets "Allow or Deny" [A1]. The classic panel uses plan approval: Claude lists the sites and approach, buttons are "Approve plan" and "Make changes" [A1]. Site prompt options: "Allow this action", "Always allow actions on this site", "Decline" [A1]. Even with always-allow, Claude still asks before downloading files, entering potentially sensitive information and granting authorisations [A1]. On protected sites a prompt appears in the side panel; the page reader returned its title once as "Permission required" and once as "New permissions required", so verify [A1].
- **6/7 Handoff and credentials.** 1Password integration: "You approve each request with biometrics, and 1Password fills the credential directly so Claude never sees your password" [A2]. Notifications are sent when Claude "requires permission or completes a task" [A2].
- **8 Tabs.** "Drag tabs into Claude's designated tab group to enable Claude to view and interact with all grouped tabs at once" [A2].
- **10 Policy.** Site permissions can be granted or revoked in Settings [A4]. Team and Enterprise admins switch the extension on or off and set site allowlists and blocklists [A1] [A5]. Never allowed in any mode: purchases and financial transactions, account creation, credit card or ID data, permanent deletions [A1]. Blocked categories: financial services, adult content, pirated content [A4] (the safety article says financial sites need permission first [A3]).
- **12 Motion.** No reduced-motion statement found. The glow animation was reported to cost about 50% CPU on an M1 Mac because box-shadow animation repaints every frame; the issue was closed as not planned [A6].
- **Screenshots found.** Anthropic's blog shows a phishing-email injection scenario before and after mitigations [A4]. A reviewer's screenshot shows four vendor-portal tabs on the left and the Claude side panel on the right [A13] `[press]`.
- **Not found:** timeline granularity, result card, error states, exact stop control.

### 1.2 Claude Cowork built-in browser (Claude Desktop)

Sources: [A7] [A8] [A9] [A13] [A14]

- **1 Layout.** The browser opens "in the side panel next to your task"; links in the task transcript open in the same panel. Claude Desktop must stay open and online even when the session is driven from web or mobile [A7]. A reviewer describes it as "a second, Claude-operated tab pane docked beside your conversation", visible "in real time as it happens, not as an opaque background process" [A13] `[press]`.
- **5 Approvals.** "Claude asks for your permission before acting on a site for the first time." High-risk sites are blocked. Safety checks "compare what Claude is doing with what you asked for" [A7].
- **6/7 Credentials.** First-run banner: "Stay signed in to your sites by importing cookies from your browser", button "Import cookies". Import is per site from Chrome, Edge or Firefox (macOS) or Firefox (Windows, Linux). Banking, email and SSO sites are unchecked by default. "Claude remembers your logins across Cowork sessions" [A7] [A8]. "Claude never sees your tabs, bookmarks, or passwords" [A8]. A reviewer notes there is no bulk import and calls this "a genuine bit of friction, by design" [A13] `[press]`.
- **10 Settings.** "Settings > Cowork" > "Preferred browser": "Built-in browser" or "Chrome (Claude in Chrome)". If the preferred one is unavailable Claude says so and asks before switching [A7]. Admin toggle at "Organization settings > Cowork"; one allowlist/blocklist governs both browsers: "The same list governs both, so there's no separate list to maintain" [A9].
- **11 Errors.** Reviewers list CAPTCHA and bot detection as unresolved failure classes [A14] `[press]`.
- **Not found:** tab strip, URL bar, takeover controls, timeline, replay.

### 1.3 Claude computer use (Cowork)

Source: [A10]

- **5 Approvals.** Claude asks before accessing each app. "Some sensitive apps (investment and trading platforms, cryptocurrency) are blocked by default." Users can add apps to a blocklist; requests for those are "automatically denied".
- **2/4 Presence and control.** Setting under "Settings > General", "When Claude requests access to an app": background mode (default on macOS 15+, Claude works in background windows without taking the pointer) or "Full control". Claude "asks for your permission the first time a task needs the full screen in each session before taking over".
- **11 Constraint.** "Your computer needs to be awake and the Claude Desktop app needs to be open."
- **Not found:** on-screen indicator while Claude controls the screen, stop shortcut.

### 1.4 OpenAI Operator (discontinued 2025-08-31)

Sources: [O18] (mirror of the launch post) [O19] [O20]

- **1 Layout.** Remote browser shown in the web app; "displays screenshots of its progress" as it works [O19] `[press]`.
- **5 Approvals.** "Before finalizing any significant action, such as submitting an order or sending an email, Operator should ask for approval" [O18]. The demo "frequently asked users for confirmation to continue" [O19] `[press]`.
- **6 Handoff.** Takeover mode: "Operator asks the user to take over when inputting sensitive information into the browser, such as login credentials or payment information." In takeover it does not collect or screenshot what the user enters [O18].
- **Watch mode.** "On particularly sensitive sites, such as email or financial services, Operator requires close supervision of its actions" [O18].
- **8 Multi-session.** Several tasks at once by opening new conversations; prompts can be saved to the home page for repeat tasks [O18].
- **10 Settings.** One click to "delete all browsing data and log out of all sites" under Privacy [O18].

### 1.5 ChatGPT agent (removed August 2026)

Sources: [O1] `[excerpt]` [O2] `[excerpt]` [O3] [O4]

- **1 Layout.** A virtual computer inside the chat, with "an on-screen narration" of what the agent is doing [O2] `[excerpt]`. NN/g describes a low-resolution embedded browser window with screenshots documenting progress [O3] `[press]`.
- **5 Approvals.** Confirmation before high-impact actions; the agent asked "Shall I go ahead and submit now?" before submitting a reservation [O3] `[press]`. Watch mode requires supervision on certain sites [O1] `[excerpt]`.
- **6 Handoff.** For logins the agent pauses and prompts the user to take control via the "..." menu > "Take over browser". "While you control the browser, screenshots are not captured" [O1] `[excerpt]`. After return, "the agent attempts to continue from the prior workflow state; in some cases it may need to re-establish the run or prompt you again" [O1] `[excerpt]`.
- **Complaints.** A reservation took about 20 minutes against about 2 by hand; 55 seconds to reach one site; a dropdown mis-click changed 12:00 to 12:15 without telling the user; the form timed out while the agent worked; the cramped window made human data entry hard [O3] `[press]`. Users who lost the feature say the replacements do not reproduce "hand control to the user for authentication before continuing" [O4].

### 1.6 ChatGPT Atlas agent mode (shut down 2026-08-09)

Sources: [O14] [O15] `[excerpt]` [O16] [O17]

- **1 Layout.** ChatGPT panel on the right of the browser window. Agent mode starts from the sidebar menu or from "+" in the composer [O14] [O16] `[press]`.
- **2 Presence.** A "weird sparkle overlay effect" over the page; a tooltip naming the current action ("Opening the first result"); a bar at the bottom with "Take control" and "Stop" [O14] `[press]` (described from Simon Willison's screenshot). Wikipedia adds agent cursor control and browser elements highlighted in blue [O17].
- **5 Approvals.** Pauses "to ensure you're watching it take actions on specific sensitive sites such as financial institutions" [O15] `[excerpt]`.
- **7 Credentials.** Logged-in versus logged-out chooser at task start; logged-out mode uses no existing cookies [O16] `[press]`.
- **10 Settings.** Page visibility toggle in the address bar decides whether ChatGPT can see the current page [O16] `[press]`. The agent cannot run code in the browser, download files, install extensions or reach the file system [O15] `[excerpt]`.
- **12 Accessibility.** The agent reads ARIA roles and names from the accessibility tree; OpenAI told site owners to follow WAI-ARIA practice [R3] `[press]`. This is about how the agent perceives pages, not about the accessibility of Atlas's own UI.
- **Complaints.** "Like watching a first-time computer user painstakingly learn to use a mouse for the first time" [O14] `[press]`. Ten minutes to add three items to an Amazon cart (The Verge) and sixteen minutes to find flights (WSJ) `[press]` `[unverified]` (secondary citation via [O23]).

### 1.7 ChatGPT Work cloud browser, ChatGPT desktop built-in browser (`@Browser`), browser extension (`@Chrome`)

Sources: [O5] [O6] [O7] `[excerpt]` [O8] [O9] [O10] [O11] [O12] [O13]

**Cloud browser (ChatGPT Work)**

- **1 Layout.** ChatGPT "uses its own browser, running on a separate computer in the cloud". A Live View panel sits in the Work conversation [O5] [O8].
- **3/9 Review.** "Page screenshots and browser replay in a Work conversation" [O6].
- **5 Approvals.** Website access setting with three levels: "Always ask", "Auto approve", "Always allow" (not recommended); per-site allow or block overrides the default [O5]. Separately, ChatGPT "will always ask for confirmation before consequential actions, such as submitting your information to book an appointment or completing a payment" [O5]. Admins can remove "Always allow" for the whole workspace [O6].
- **6/7 Handoff and credentials.** At a login screen ChatGPT "pauses and asks you to enter your credentials and two-factor authentication codes as needed" in a secure form; the model cannot see the credentials and they are not stored. Alternative link: "Sign in on web page instead", which lets the user sign in directly in the cloud browser while the task pauses [O5]. A review model checks for phishing before the sign-in request is shown, and the user can "preview the sign-in page and the live form before continuing" [O9] `[press]`. The user can "take over its computer and use it yourself on mobile and desktop" [O5]. Sessions persist until they expire [O9] `[press]`.
- **10 Settings.** "Settings > Cloud browser > Browser data > Clear all" removes cookies and signs out of sites [O5].
- **11 Errors.** "Some websites block access. If that happens, ChatGPT will let you know and, when possible, try another way to complete the task" [O5]. Takeover can fail: red toasts "Unable to take over the browser", "You can't take over the browser right now. Please try again." and a black Live View panel; the reporter asks for a session identifier on failure and for stale sessions to reset without losing chat state [O8].

**Built-in browser in the desktop app**

- **1 Layout.** Tabs open with "New tab" or Cmd+T. "Enter full view" expands the tab; "Enter split view" shows chat and tab side by side [O5].
- **Annotation.** "Annotate" mode: click an element or select an area and leave a comment; an "Adjust" option tunes font, spacing and colour with live preview [O5]. The comment carries "the screenshot and element context, so I do not have to describe the whole page again" [O12] `[press]`.
- **Downloads.** System Downloads folder by default; "Settings > Browser" offers "Ask where to save downloads" [O5].

**Browser extension (`@Chrome`, also Edge, Brave, Vivaldi, Opera)**

- **1 Layout.** Side chat beside the page; right-click "Ask ChatGPT" on a selection; tabs can be @-mentioned from the desktop app [O11].
- **5 Approvals.** Four options: "Allow once", "Allow for this site", "Allow for all sites" (labelled "Elevated Risk"), "Decline" [O11]. (A third-party write-up lists "Allow this chat", "Always allow", "Decline" instead; the vendor doc is the one to trust [O13] `[press]`.)
- **8 Tabs.** One Chrome tab group per conversation thread, so several threads can work in parallel [O13] `[press]`.
- **10 Settings.** "Settings > Computer Use > Manage": Allowlist ("Domains ChatGPT can use without asking again") and Blocklist ("Domains ChatGPT shouldn't use") [O11]. Browser history access prompts every time with no persistent allow [O11].

### 1.8 Perplexity Comet

Sources: [P1] [P2] `[excerpt]` [P3] `[excerpt]` [P4] [P5]

- **1 Layout.** A "sidecar" assistant pane on the right of any page [P1] `[press]` [P4] `[press]`.
- **2/3 Presence and timeline.** "You can watch while Comet works or see its reasoning step-by-step in the Assistant sidecar, and you'll see exactly where it's clicking, scrolling, or interacting with a site" [P2] `[excerpt]`. A reverse-engineering write-up says the sidecar renders tool calls, intermediate results and decision points as they stream [P4] `[press]`.
- **4 Controls.** "Clear buttons to stop the Assistant or provide more guidance" [P2] `[excerpt]`.
- **5 Approvals.** When a task could be delegated, the user can browse themselves, allow the assistant once, or let it browse automatically in future [P2] `[excerpt]`. First-run prompt for an advanced agent: "Allow this time only", "Always allow", "Don't allow" [P3] `[excerpt]`.
- **8 Multi-session.** Background Assistant (Max plan): "a team of assistants working for you" tracked from a central dashboard "like a mission control"; the user can check progress, "jump in to complete the tasks, like hitting send on the email", intervene or take over, and is notified on completion [P1] `[press]`.
- **10 Policy.** Enterprise admins can disable assistant actions, remove the "Always Allow" option (forcing a prompt every time), and set domains to "Read Only" or "No Access" [P3] `[excerpt]`.
- **11 Errors.** A visible refusal when the agent is asked to open a blocklisted URL [P4] `[press]`.
- **Complaints.** Agent "getting stuck in loops", booking a hotel for the wrong dates, "taking so long that it would have been faster to do it yourself"; memory above 4 GB with few tabs [P5] `[press]`.
- **Not found:** agent cursor or glow, replay, result card.

### 1.9 Chrome auto browse (Gemini in Chrome), Gemini Agent/Spark remote browser, Project Mariner

Sources: [G1] [G2] [G3] [G4] [G5] [G6] [G7] [G8]

**Chrome auto browse (active)**

- **1 Layout.** Gemini side panel on the right; the agent works in its own tab while the user can "continue to visit other sites as auto browse works in the background" [G2] [G3] `[press]`. On Android it is a bottom sheet; minimising it leaves "a docked progress bar" [G4] `[press]`.
- **2 Presence.** The task tab is "badged by a cursor and sparkle icon" and has "a glow around it"; Chrome also shows that auto browse is active in the top-right corner next to the Gemini spark [G3] `[press]`. On Android "a blue glow around the webpage" and a ring around the Gemini icon [G4] `[press]`.
- **3 Timeline.** The side panel "shows step-by-step what it's doing" [G3] `[press]`.
- **4 Controls.** Plan first: the user reviews the plan Gemini creates, then clicks "Start Task". During the run: "Take over task" on the task tab, "Resume" or "Give back task" in the chat, "Stop", and a "Switch tabs" link to jump to the working tab [G1].
- **5 Approvals.** Explicit approval before finalising financial transactions, accepting terms of service, creating accounts, sending communications, submitting web forms, scheduling events, and before using sensitive financial or health sites [G1]. For purchases and social posts the user must press the final button themselves [G3] `[press]`. One reviewer saw "a confirmation message saying explicitly that purchases require human approval, with a one-click Approve button" and drafts that stop "at the Send button" for review [G5] `[press]`.
- **6 Handoff.** When help is needed auto browse pauses and a "Check your task" notification appears at the top of the browser; the user clicks "Take over task", does the manual step ("accepting cookies, signing in, or entering a CAPTCHA") and clicks "Resume" [G1].
- **7 Credentials.** Google Password Manager can sign in after the user authorises it; "Google does not share passwords with Gemini". Managed under "Sites Gemini can sign you in to" [G1].
- **10 Settings.** Off switch: Settings > AI innovations > Gemini in Chrome > "Let Gemini browse for you" [G1]. Caps: 20 multi-step tasks a day on AI Pro, 200 on AI Ultra [G1].
- **Screenshots found.** Google's blog shows an Expedia booking with the side panel offering "Take over task"; caption: "Auto browse capabilities are designed to keep you in the loop and ask for confirmation of sensitive actions" [G2].
- **Complaints.** Stalls on confirmation modals it cannot parse; cancelled the wrong subscription tier; long tasks time out; "does not yet coordinate well with tabs you are actively using in the same window" [G5] `[press]`. The side panel shrinks the page area [G6] `[press]`.

**Gemini Agent / Gemini Spark remote browser (active)**

- A "Remote computer icon at the top of the task thread" opens the live view. Hovering it shows "Take over task"; "Go back to Gemini" returns control. "Stop" exists in the side panel and in the text box. A work panel has "Progress", "Files" and "Schedules" sections. Sign-in: confirm "Sign in with Google" when available, otherwise take over and sign in manually. Up to 15 tasks can run at once [G7].

**Project Mariner (shut down 2026-05-04)**

- Up to 10 simultaneous tasks at its peak; described as resource-heavy with slow performance and small errors on complex pages [G8] `[press]`. No UI detail found.

### 1.10 Microsoft Edge: Browse with Copilot (formerly Copilot Actions / Copilot Mode)

Sources: [M1] [M2] [M3] [M4]

- **1 Layout.** Started from the Copilot text box with "Browse with Copilot". The agent works in a spawned tab; a "Watch Progress" button switches to it [M1] [M3] `[press]`.
- **2 Presence.** "The tab where Copilot is working shows a cursor icon in the tab menu, so you can easily locate it" [M1]. The agent uses "a pointer with splash marks" [M3] `[press]`.
- **4 Controls.** "You can interrupt or take control at any time" [M1]. Stop is "the square stop button in your text entry box" [M3] `[press]`.
- **5 Approvals.** Copilot asks for attention before "buying an item, booking a reservation, sending an email, or deleting a calendar event" and asks for supervision "on higher-risk sites like banking or email" [M1].
- **6 Handoff.** "If a task requires your input, such as personal details or payment information, Copilot will ask you to provide it, and you can take control" [M1]. In Edge for Business, "for sensitive actions such as entering passwords or credit card numbers, Copilot pauses for user input" [M2].
- **9 Review.** Screenshots of pages are stored up to 30 days as history for troubleshooting and review [M1].
- **10 Policy.** Blocklists for high-risk sites (adult, gambling) [M1]. In Edge for Business, admins scope agentic browsing to designated sites; Purview data-protection rules still apply while Copilot browses [M2]. A toggle "Allow Cowork to take actions on your behalf" [M4] `[press]`.
- **Start-of-run warning.** "Actions in Edge Preview is intended for research and evaluation purposes. Copilot can make mistakes. Please monitor results closely." [M3] `[press]`
- **Complaints.** Stalled several times and "failed to type in column headers" [M3] `[press]`.

### 1.11 Opera Neon (Neon Do)

Sources: [N1] [N2] [N3] [N4]

- **1 Layout.** Tasks are "self-contained workspaces"; Neon Do acts inside the user's real, logged-in browser session, within a Task's own tabs [N1].
- **2/4.** "Its actions are visible in real time, with the option to pause or take control at any moment" [N1]. When it cannot proceed alone, "the 'Do' tab at the top of the screen will flash red" [N2] `[press]`.
- **7 Credentials.** Runs where the user is already logged in, so no password sharing [N1].
- **Complaints.** The Verge, as relayed by [N2] `[press]`: no way to course-correct the agent while it acts; it ignored the reviewer's clicks, added the wrong item to the cart and wrongly declared a show sold out. Another reviewer: "It's slow, and it acts dumb" [N4] `[press]`.

### 1.12 Manus

Sources: [U1] [U2] [U3] [U4] [U5] [U6] [U7]

- **1 Layout.** Chat on one side, a "Manus's Computer" side panel showing the steps and the live browser [U5] `[press]` [U7] `[press]`.
- **2 Presence.** A "Manus is working" status line with a floating chip showing elapsed time (for example "Manus is working 0:08") that stays visible while scrolling; the composer stays usable so the user can steer mid-run [U6] `[press]`.
- **3 Timeline.** Cards name the artefact being touched ("Editing files") with an expandable preview [U6] `[press]`.
- **4/6 Handoff.** When Manus meets "complex verifications (SMS codes, CAPTCHA, multi-factor authentication), the system will prompt you to 'Take Over' the browser"; the user completes it and hands back. Users can also take over on their own initiative [U1] [U4]. "Take Over Notifications" is a settings item [U1].
- **7 Credentials.** The cloud browser keeps logged-in sessions. "Settings > Cloud Browser > Logged-in Accounts" lists them, with per-account logout and clear-all. "Manus doesn't store passwords" [U1]. Guidance: watch the first login on each account [U1].
- **8 Tabs (Browser Operator, local).** After the user toggles the "My Browser" connector, Manus requests permission per task; "Authorize" grants one-time access. "Manus opens a new tab within a tab group named after your current task." The user can "take over by clicking into the tab, or stop the process instantly by closing it" [U2] [U3].
- **9 Review.** "Each session is replayable and shareable" [U5] `[press]`. Completion shows a green check chip labelled with the task intent and a count ("1/1"), plus source thumbnails; slide decks open in a filmstrip preview [U6] `[press]`.
- **11 Errors.** "Due to the current high service load, tasks cannot be created"; the Computer panel "froze on a certain page for a long period"; frequent CAPTCHA blocks on news sites, where the reviewer wanted Manus to "proactively ask for help" [U5] `[press]`. The vendor notes that data-centre IPs trigger extra verification and recommends the local browser for sensitive accounts [U1].
- **Not found:** replay scrubber detail, exact takeover and hand-back button labels.

### 1.13 Browserbase (live view, session inspector, Director)

Sources: [B1] [B2] [B3] [B4]

- **1 Layout.** Live view is an iframe URL. `debuggerFullscreenUrl` gives a bare view; `debuggerUrl` adds browser-like borders. A navbar at the top gives context and can be removed with `&navbar=false` [B1]. Mobile embedding by setting the viewport (example 360x800); "Mobile keyboards aren't officially supported" [B1].
- **6 Handoff.** Read-only embed uses `pointer-events: none`; removing it makes the view interactive. Use cases named: credential delegation, iframes, file upload [B1].
- **8 Tabs.** "Each tab has a unique live view url"; the host app listens for new-tab events and fetches the new URL [B1].
- **9 Review.** Session Inspector: video replay with speed 0.5x, 1x, 2x, 4x (up to 10 tabs); an Events and Pages timeline (pages, CDP events, network); Console; Network; and a Stagehand tab whose rows expand to token usage, execution time, schema and result. A status bar shows session ID, status, start time, region, duration and proxy bandwidth. Retention 31 days [B2] [B3]. Console also logs "browser-solving-started / browser-solving-completed" captcha events [B3].
- **11 Errors.** On session end the view shows a disconnect message and posts `"browserbase-disconnected"` to the host window [B1].
- **Director.** Natural-language prompt in, a Stagehand script out; the user chats with the app and watches the agent work [B4]. No UI detail found beyond that.

### 1.14 Browser Use Cloud

Sources: [BU1] [BU2] [BU3]

- **1 Layout.** `live_view_url` arrives in the `browser.ready` event. Recommended embed is a 16:9 iframe. The live view includes tabs and a toolbar by default; `ui=false` hides them but "does not disable interaction" [BU2].
- **6 Handoff.** "Open the live browser, take over, then continue the same session." A follow-up run with the same `session_id` reuses the live browser. Use cases: approvals, authentication, payments, review checkpoints [BU1].
- **9 Review.** Optional MP4 recording, available after the browser stops; zero-data-retention projects never record. Shared sessions expose the recording but never the interactive live view [BU2] [BU3] `[excerpt]`.
- **12 Accessibility.** The documented read-only embed wraps the iframe in `<div inert>`, sets `tabindex="-1"`, `pointer-events: none` and `title="Live browser preview"` [BU2]. The vendor states that view-only is "a UI restriction, not a server-enforced permission" [BU2].
- **Security.** "Treat live-view URLs as credentials" [BU1].

### 1.15 Steel

Sources: [S1] [S2] [S3] [S4]

- **1 Layout.** Session viewer embeds via `debugUrl`. `interactive=true` (default) allows remote mouse and keyboard; `interactive=false` gives a "read-only, watch-only view". Legacy headless sessions also take `theme` (dark or light), `showControls`, `pageId`, `pageIndex` [S1].
- **Live-view transport.** Steel replaced Chrome screencasting ("4-12fps, unstable", "designed for DevTools, not production streaming") with OS-level WebRTC at 25 fps. Screencast "couldn't handle OS-level elements like native alerts or permission dialogs, these would be invisible in the stream", and frame rate "varied wildly depending on page complexity" [S2].
- **3/9 Timeline and replay.** Agent Traces: each row "reads like a sentence" (`click on Sign in`, `input(len=17) on Email field`, `navigate to /home`); keystrokes collapse to one row; idle gaps become dividers (`idle 23s`). Clicking a row seeks the video to that frame. The scrubber carries colour-coded ticks per action with hover thumbnails. A row drawer shows element tag, role, accessible name, bounding box, selectors, coordinates, URL, raw JSON and a frame thumbnail. "Copy as markdown" exports the trace for pasting into another agent [S3]. Agent Logs: event type, timestamp, target element; filter by navigation, click or keyboard [S4].
- **Replay format.** Moved from rrweb DOM replay to MP4 because "if an event wasn't captured correctly, the replay would diverge from reality" [S2].
- **Security.** "Debug URLs are unauthenticated"; put your own access control in front [S1].

### 1.16 Skyvern

Sources: [K1] [K2] [K3] [K4]

- **1 Layout.** Live run screen has three panels: left shows "the block being executed, its URL, and prompt" plus a status badge; centre shows the live browser; right shows "real-time LLM reasoning and action decisions" [K1].
- **3 Timeline.** Three card types: Thought (reasoning), Block (workflow block status) and Action (one browser operation). Counters for Actions and Steps [K2].
- **4 Controls.** "Take Control" pauses the agent and gives the user mouse and keyboard; "Release Control" resumes "from whatever state you left the browser in"; control can change hands many times in a run. "The task timer keeps running, so release control promptly to avoid timeouts" [K1]. "Cancel" in the header; "Credits for actions already taken are still consumed" [K1]. After completion: "Rerun", "Edit", "API & Webhooks" [K2].
- **5 Approvals.** Human-approval step renders "a review card showing Approve and Reject buttons and a status chip reading paused" [K4].
- **7 Credentials.** A Credentials section stores logins, payment cards and secrets; a searchable picker; passkey and email-based 2FA retrieval; credential pools with fallback [K3] [K4].
- **9 Review.** Tabs: Overview (screenshots plus timeline), Output (JSON and downloaded files), Parameters, Recording (video with scrubbing), Code. Success shows "Extracted Information"; failure shows a "Failure Reason" section in red [K2].
- **State names.** created, queued, running, completed, failed, terminated, canceled, timed_out [K2]. The live stream closes at any final state and the recording takes over [K1].

### 1.17 Amazon Nova Act human-in-the-loop

Source: [W1]

- Two patterns. Human approval: Nova Act "captures a screenshot of the current state and presents it to a human reviewer via a browser-based interface" for binary or multiple-choice decisions. UI takeover: "hands control of the browser to a human operator via a live-streaming interface" for CAPTCHA and login or MFA.
- The optional Human Intervention Service gives supervisors a "one-off action interface" for quick decisions and a "supervisor dashboard" of pending requests, history and metrics. Notifications go to Slack (threaded) or email.
- Guidance: timeouts sized to the task ("login interventions might need longer timeouts than CAPTCHA resolutions"), handle timeout and rejection, log every intervention.

### 1.18 AWS Bedrock AgentCore Browser

Source: [W2]

- **Live view.** Opens in a new window from a "View live session" link on sessions with status Ready or In progress. It offers a real-time video stream, "interactive controls to take over or release control from automation", status and connection indicators, and resolution change on the fly.
- **Replay.** "View Recording" on Terminated sessions: video player with timeline scrubber; a Pages panel with time ranges; User Actions (timestamp, method, details); Page DOM; Console Logs; CDP Events; Network Events. Clicking a page or an action jumps the video. The sample viewer adds "action markers on timeline showing form fills, clicks, and navigation events".

### 1.19 Cloudflare Browser Run

Sources: [C1] [C2] [C3]

- **Live view modes.** `tab` ("one selected page without DevTools panels"), `full` (browser interface with tabs), `devtools` [C2]. Reachable from the dashboard's Live Sessions tab or a signed URL on `live.browser.run` [C2].
- **Structured handoff.** The script sends `Cloudflare.handoff` with instructions and waits for `Cloudflare.handoffComplete`. The human opens the live view, does the step and selects "Done" or "Failed". Maximum timeout 30 minutes; 2 to 3 minutes suggested for quick steps, 10 to 15 for complex ones [C1].
- **Limit stated by the vendor.** "Browser Run requests are always identified as bot traffic. Even with a human controlling the session, some third-party services may still block the request" [C1].
- **Security.** Live view URLs carry a signed token, valid 5 minutes by default and up to 1 hour [C2].
- **Recording.** DOM-state recordings under Browser Run > Runs [C3]. The changelog GIF shows an agent hitting an Amazon sign-in and asking a human for help [C3].

### 1.20 Hermes Agent (Nous Research)

Sources: [H1] [H2]

- **Dashboard.** Local web app with pages for Status, Chat (the terminal UI embedded through xterm.js), Sessions, Logs, Analytics, Cron and more [H1].
- **8 Multi-session.** Session rows show title, source icon, model, message count, tool-call count and last activity; "Live sessions are marked with a pulsing badge" [H1].
- **3 Timeline.** Session detail: messages colour-coded by role; tool calls as "collapsible blocks with the function name and JSON arguments" [H1].
- **9 Counters.** Analytics: total tokens, cache hit rate, cost, sessions, per-day and per-model breakdown [H1].
- **Browser surfaces.** No embedded live view in the dashboard was found. Options are a visible headed window (`browser.headed: true`), attaching to the user's own Chrome (`/browser connect`), a VNC URL included in navigation responses, WebM session recordings kept 72 hours, and screenshots sent to chat platforms as photo attachments [H2].
- **12.** Theme list includes a "Large" variant and a font override [H1].

### 1.21 OpenClaw

Sources: [X1] [X2] [X3] [X4]

- **2 Presence.** The agent's managed browser uses a dedicated profile named "openclaw" with an orange accent, separate from the user's own profile [X1]. The relay extension badge has three states: "ON" (attached), "…" (connecting), "!" (relay unreachable) [X4] `[excerpt]`.
- **1 Layout.** The Control UI has a Browser panel beside conversations and approvals [X1]. No detail found.
- **5 Approvals.** Three actions: "Allow once", "Allow always", "Deny". The card shows the command with working directory and an expandable "Details" for the executable path. If no UI is reachable or the prompt times out, the fallback is deny by default. Approvals can also be answered from chat with `/approve <id> allow-once|allow-always|deny` or reaction shortcuts [X2].
- **6 Handoff.** Sign in manually in the openclaw profile; "manual login is recommended because automated logins often trigger anti-bot defenses and can lock the account" [X3] `[excerpt]`.

---

## 2. Pattern table

"Best variant" is my judgement from the evidence above, not a vendor claim.

| # | Pattern | Who uses it | Variant that seems to work best, and why | Pitfalls reported |
|---|---|---|---|---|
| 1 | Chat/task column beside a browser pane | Cowork built-in browser [A7], ChatGPT desktop (split/full view) [O5], Manus [U5], Skyvern (three panels) [K1], ChatGPT agent [O3] | Split view with a one-click switch to full view ("Enter full view" / "Enter split view"). Takeover needs the large view; watching needs the small one | A cramped, low-resolution pane makes human data entry hard [O3] |
| 2 | Side panel inside the user's own browser | Claude in Chrome [A2], Chrome auto browse [G2], Comet [P1], Atlas [O14], ChatGPT extension [O11] | Fits logged-in tasks with no credential transfer | Panel shrinks the page [G6]; broad extension permissions cause hesitation [A12] |
| 3 | Agent-owned tab group or tab | Claude in Chrome (different colour) [A2], ChatGPT extension (group per thread) [O13], Manus Operator (group named after the task) [U3], Edge and Chrome (own tab) [M1] [G3] | Group named after the task plus a distinct colour. The user sees at a glance what is the agent's and can keep browsing | Agent and user colliding in the same window [G5] |
| 4 | Glow or border on the controlled page | Claude in Chrome [A6], Chrome auto browse [G3] [G4], Atlas (sparkle) [O14] | A calm border with a text label. It marks "agent-owned" without hiding content | Animated box-shadow cost about 50% CPU [A6]; Atlas's effect was called "weird" [O14] |
| 5 | Tab badge or icon | Chrome (cursor and sparkle) [G3], Edge (cursor icon) [M1], OpenClaw (ON / … / !) [X4], Neon (tab flashes red when stuck) [N2] | Badge with distinct states: working, needs you, disconnected | Colour-only signalling |
| 6 | Agent cursor distinct from the user's | Edge ("pointer with splash marks") [M3], Atlas [O17], Comet ("see exactly where it's clicking") [P2] | Styled pointer plus a click ripple | None reported; slow cursor travel adds to the "watching it learn the mouse" impression [O14] |
| 7 | Caption of the current action | Atlas tooltip ("Opening the first result") [O14], ChatGPT agent narration [O2], Manus status line with timer [U6], Skyvern block/URL/prompt panel [K1] | One plain-language line near the page, plus elapsed time | Narration that hides a silent change (12:15 for 12:00) [O3] |
| 8 | Plan, then one approval to start | Claude in Chrome classic ("Approve plan" / "Make changes") [A1], Chrome auto browse ("Start Task") [G1], Gemini Spark [G7] | A plan card that lists the sites to be used. One decision scopes the run | Extra step for trivial tasks; ChatGPT agent was criticised for not asking clarifying questions first [O3] |
| 9 | Three-level autonomy switch | Claude (Manual / Auto / Skip) [A1], ChatGPT cloud browser (Always ask / Auto approve / Always allow) [O5], Comet [P2] | Middle level as default, backed by an automatic safety check, with hard gates that no level removes | Manual mode produces approval fatigue: users approve 93% of prompts [A11]. Fully open mode loses control |
| 10 | Per-site permission prompt | Claude [A1], ChatGPT extension [O11], Comet [P3], OpenClaw [X2], Manus Operator ("Authorize") [U3] | Three or four options: once, always for this site, deny; "all sites" only with a risk label ("Elevated Risk") | Prompts at unpredictable times make it hard to step away `[unverified]` [R1] |
| 11 | Hard gate on consequential actions in every mode | Claude [A1], Chrome [G1], ChatGPT Work [O5], Edge [M1], Operator [O18] | Stop at the final button and show the draft. Chrome makes the user press Buy or Post personally [G3] | Over-asking (Operator "frequently asked") [O19]; agent stops without saying why |
| 12 | Watch mode on sensitive sites | Operator [O18], ChatGPT agent [O1], Atlas [O15], Edge [M1] | Pause when the user is not looking at the agent's tab | Forces the user to babysit |
| 13 | Take over and hand back | All consumer and infra products | Two explicit buttons (Skyvern "Take Control" / "Release Control"; Chrome "Take over task" / "Resume"; Gemini "Go back to Gemini"). Agent paused, screenshots off, timer visible | Takeover fails with no recovery [O8]; timer keeps running [K1]; no way to correct mid-action [N2] |
| 14 | Agent-requested handoff with a notification | Chrome ("Check your task") [G1], Manus [U1], Claude [A2], Nova Act (Slack, email) [W1], Cloudflare (`handoff`) [C1] | A request that states the reason and what to do, with "Done" / "Failed" answers and a timeout [C1] | Agent hits a wall and does not ask [U5] |
| 15 | Credentials kept away from the model | ChatGPT Work secure form [O5], 1Password [A2], Google Password Manager [G1], Cowork cookie import [A7], Skyvern vault [K3] | Out-of-band form plus a fallback to sign in on the page itself ("Sign in on web page instead") | Per-site friction [A13]; data-centre IPs trigger more challenges [U1] |
| 16 | Typed timeline cards | Skyvern (Thought / Block / Action) [K2], Steel (sentence rows) [S3], Hermes (collapsible tool calls) [H1] | Sentence-style rows, keystrokes collapsed, idle gaps shown, detail drawer on demand | Raw CDP event lists are too noisy for end users |
| 17 | Replay synced to the timeline | Steel [S3], AgentCore [W2], Browserbase [B3], Skyvern [K2], ChatGPT Work [O6], Manus [U5] | Real video with action ticks on the scrubber and click-to-seek from any row | DOM-based replay can diverge from reality [S2] |
| 18 | Background task dashboard | Comet [P1], Gemini Spark (15 tasks) [G7], Operator [O18], Hermes (pulsing live badge) [H1], Nova Act supervisor dashboard [W1] | Rows with status, progress and a "needs you" flag; open any row to jump in | None reported in sources |
| 19 | Result and deliverables | Skyvern ("Extracted Information" / "Failure Reason") [K2], Manus completion chips [U6], Gemini Spark "Files" [G7] | Result card restating the task, with files and a link to the replay | Agent reports success wrongly (Neon "sold out") [N2] |
| 20 | Org policy | Claude [A9], Comet ("Read Only", "No Access") [P3], ChatGPT Work [O6], Edge for Business [M2] | One list shared by all browser surfaces [A9]; admin can remove the "always allow" option [O6] [P3] | Not found |
| 21 | Live-view link treated as a secret | Browser Use [BU1], Steel [S1], Cloudflare [C2] | Short-lived signed URL (5 minutes default) [C2] | View-only that is only a UI restriction [BU2] |

---

## 3. Component inventory

Each row lists purpose, required states and key data. Source IDs point to a product that ships the component.

| Component | Purpose | Required states | Key data shown |
|---|---|---|---|
| Task composer | Start a task; steer or queue follow-ups mid-run | empty, typing, submitting, locked during takeover, steering allowed during run [U6] | Task text, autonomy mode selector, start-site hint |
| Autonomy mode selector | Choose how often the agent asks | Manual, Auto (default), Skip; option disabled by admin [A1] [O6] | Mode name, one-line consequence, risk label on the open mode |
| Plan card | Agree scope before acting | proposed, editing, approved, rejected [A1] [G1] | Steps, sites to be used, "Approve plan" / "Make changes" |
| Run status chip | Say what the run is doing now | one per state in section 4 | State word, current action sentence, elapsed time [U6] |
| Live browser frame | Show the real page | connecting, live, stale, paused, human-in-control, ended, disconnected [B1] [O8] | Stream, URL bar, tab strip, connection quality |
| URL bar | Show where the agent is | loading, loaded, blocked by policy | Scheme and host emphasised, lock or warning |
| Tab strip | Show the agent's tabs | active tab, background tab, tab needing attention [B1] [C2] | Title, favicon, per-tab state badge |
| Control-state border | Mark who is driving | agent (calm border and label), human (different colour), none [A6] [G3] | Label such as "Agent is working" or "You're in control" |
| Agent cursor and click ripple | Show where the agent acts | moving, clicking, typing [M3] | Pointer position |
| Element highlight | Show the target of the next action | targeting, acted | Bounding box; in the detail drawer: role and accessible name [S3] |
| Action caption | Explain the current action in words | updating, idle [O14] | Verb and object ("Opening the first result") |
| Activity timeline | History of the run | streaming, complete, filtered [K2] [S3] | Typed cards: thought, action, approval, handoff, error; time; grouping by step |
| Step detail drawer | Evidence for one step | collapsed, expanded [S3] | Screenshot, element info, URL, duration, raw data |
| Searches panel | Queries the agent ran | streaming, complete | Query, source count (NN/g counted 10 searches and 96 sources in one ChatGPT agent run [O3]; no product in scope documents a dedicated searches panel) |
| Site permission prompt | First access to a site | pending, allowed once, always allowed, declined [A1] [O11] | Site, why the agent needs it, the three or four options |
| Action approval card | Gate a consequential action | pending, approved, rejected, expired [K4] [W1] | Action in plain words, screenshot crop of the target, amounts and recipients, reason, status chip "paused" |
| Handoff card | Ask the human to do a step | requested, human active, done, failed, timed out [C1] [G1] | Reason (login, 2FA, CAPTCHA, payment), instruction, "Take over" and "Done" / "Failed", countdown |
| Secure sign-in form | Enter credentials outside the model's view | idle, submitting, 2FA needed, failed [O5] | Site identity, username, password, code field, "Sign in on web page instead" |
| Takeover toolbar | Human drives the browser | requesting, active, releasing, failed [K1] [O8] | "Release control" button, privacy note that screenshots are off, timer |
| Stop control | End the run | idle, confirming, stopping [G1] [M3] | "Stop"; note about what is kept and what is still charged [K1] |
| Result card | State the outcome | success, partial, failed, stopped [K2] | Answer, restated task, files, link to replay, steps, time, cost |
| Artifacts list | Files produced or downloaded | empty, listing [K2] [G7] | Name, type, size, source page |
| Replay player | Review afterwards | loading, playing, paused, seeking, unavailable [S3] [W2] | Video or screenshot sequence, scrubber with action ticks, speed [B3], page list |
| Run list / dashboard | Many runs at once | queued, running, needs you, done, failed [P1] [H1] | Title, state badge, live indicator, last activity, counters |
| Notifications | Reach the user when away | needs approval, needs takeover, finished, failed [A2] [G1] [W1] | Task name, reason, deep link |
| Site permissions settings | Review and revoke grants | list, empty, admin-locked [O11] [A9] | Allowlist, blocklist, per-site mode |
| Browser data settings | Manage the agent's logins | list, clearing [O5] [U1] | Logged-in accounts, per-site logout, "Clear all" |
| Policy banner | Explain a block | blocked by admin, blocked category, read-only site [P3] [A4] | Rule that applied, who set it |
| Error panel | Recover from failure | bot wall, site blocked, budget exhausted, timeout, disconnected, service busy | Cause, what was tried, next action, session ID [O8] |
| Counters | Cost and effort | live, final [K2] [H1] | Steps, actions, elapsed time, tokens or cost |

---

## 4. State model for a run

States as the products present them. The last column shows product vocabulary where I found it.

| State | What changes in the UI | Seen as |
|---|---|---|
| Idle | Composer active; no browser frame, or last page dimmed | Skyvern `created` [K2] |
| Queued | Chip "Queued"; cancel available | Skyvern `queued` [K2] |
| Planning | Plan card streams; browser not yet moving | Chrome auto browse plan review [G1]; Claude classic plan [A1] |
| Awaiting plan approval | Plan card with two buttons; nothing else proceeds | "Approve plan" / "Make changes" [A1]; "Start Task" [G1] |
| Acting | Agent border, cursor, caption, timer; timeline grows; "Take over" and "Stop" visible | "Manus is working 0:08" [U6]; Skyvern `running` [K2]; tab badge and glow [G3] |
| Waiting for approval | Agent paused; approval card pinned; chip "paused"; notification sent | Skyvern review card [K4]; Chrome confirmation [G5] |
| Needs human (agent asked) | Banner or notification; handoff card with reason and "Take over" | "Check your task" [G1]; Manus "Take Over" prompt [U1]; Neon tab flashes red [N2] |
| Human in control | Border changes to human colour; input goes to the page; screenshots off; "Release" button; timer still visible | "Take Control" / "Release Control" [K1]; "Take over task" / "Resume" [G1]; "Go back to Gemini" [G7] |
| Blocked | Agent cannot continue: bot wall, policy block, site refuses automation. Error panel with next steps | "Some websites block access..." [O5]; Comet refusal [P4] |
| Done | Live stream ends, replay available; result card; counters final | Skyvern `completed` [K2]; Manus completion chip [U6] |
| Failed | Result card in failure style with a reason | "Failure Reason" [K2]; Skyvern `failed`, `timed_out` [K2] |
| Stopped | User ended it; partial results kept | Skyvern `canceled` [K2]; "Stop" [G1] |
| Disconnected | Frame shows a disconnect message; reconnect or view replay | `browserbase-disconnected` [B1]; black Live View panel [O8] |

Transitions worth specifying because products get them wrong: human-in-control back to acting (agent must re-read the page, "resumes from whatever state you left the browser in" [K1]); takeover request that fails [O8]; handoff timeout [C1]; approval timeout defaulting to deny [X2].

---

## 5. Microcopy examples

Quoted as returned by the page reader; verify before reuse.

**Autonomy and permissions**

- "Manually approve (Manual)" / "Automatically approve (Auto)" / "Skip all approvals (Skip)" (Claude in Chrome [A1])
- "Always ask" / "Auto approve" / "Always allow" (ChatGPT cloud browser [O5])
- "Allow this action" / "Always allow actions on this site" / "Decline" (Claude in Chrome [A1])
- "Allow once" / "Allow for this site" / "Allow for all sites" / "Decline" (ChatGPT extension [O11])
- "Allow this time only" / "Always allow" / "Don't allow" (Comet [P3] `[excerpt]`)
- "Allow once" / "Allow always" / "Deny" (OpenClaw [X2])
- "Approve plan" / "Make changes" (Claude in Chrome classic [A1])
- "Start Task" (Chrome auto browse [G1])
- "Let Gemini browse for you" (Chrome setting [G1])

**Takeover and handoff**

- "Take over task" / "Resume" / "Give back task" (Chrome auto browse [G1])
- "Go back to Gemini" (Gemini Spark [G7])
- "Take Control" / "Release Control" (Skyvern [K1])
- "Take control" / "Stop" (Atlas [O14] `[press]`)
- "Take over browser" (ChatGPT agent [O1] `[excerpt]`)
- "Check your task" (Chrome notification [G1])
- "Watch Progress" (Edge [M3] `[press]`)
- "Done" / "Failed" (Cloudflare handoff [C1])
- "Authorize" (Manus Browser Operator [U3])

**Credentials**

- "Sign in on web page instead" (ChatGPT cloud browser [O5])
- "Stay signed in to your sites by importing cookies from your browser." / "Import cookies" (Cowork built-in browser [A7])
- "You approve each request with biometrics, and 1Password fills the credential directly so Claude never sees your password." (Claude in Chrome [A2])
- "Sites Gemini can sign you in to" (Chrome setting [G1])

**Status and narration**

- "Manus is working 0:08" (Manus [U6] `[press]`)
- "Opening the first result" (Atlas tooltip [O14] `[press]`)
- "Shall I go ahead and submit now?" (ChatGPT agent [O3] `[press]`)
- Steel trace rows: "click on Sign in", "input(len=17) on Email field", "idle 23s" [S3]

**Warnings and errors**

- "Actions in Edge Preview is intended for research and evaluation purposes. Copilot can make mistakes. Please monitor results closely." (Edge [M3] `[press]`)
- "Some websites block access. If that happens, ChatGPT will let you know and, when possible, try another way to complete the task." (ChatGPT [O5])
- "Unable to take over the browser" / "You can't take over the browser right now. Please try again." (ChatGPT Work [O8])
- "Due to the current high service load, tasks cannot be created" (Manus [U5] `[press]`)
- "Credits for actions already taken are still consumed." (Skyvern [K1])
- "The task timer keeps running, so release control promptly to avoid timeouts." (Skyvern [K1])

---

## 6. What reviewers and users complain about

1. **Slowness.** The dominant complaint. ChatGPT agent: about 20 minutes for a 2-minute booking [O3]. Atlas: "like watching a first-time computer user painstakingly learn to use a mouse" [O14]. Claude in Chrome: "Simple tasks that take you seconds can take Claude minutes" [A12]. Comet: "faster to do it yourself" [P5]. Neon Do: slower than doing it by hand [N2]. Project Mariner was shut down partly for being slow and resource-heavy [G8]. All `[press]`.
2. **Silent wrong outcomes.** Booked 12:15 instead of 12:00 without flagging it [O3]; cancelled the wrong subscription tier [G5]; declared a show sold out when it was not [N2]; hotel booked for the wrong dates [P5].
3. **Losing control mid-run.** No way to course-correct Neon Do while it acts, and it ignored the user's clicks [N2]. Chrome auto browse collides with tabs the user is using [G5].
4. **Takeover that breaks.** ChatGPT Work takeover failing with only "Please try again", blocking sign-in and burning paid usage [O8]. Skyvern's timer running during human control [K1]. Cramped takeover window [O3].
5. **Approval fatigue and babysitting.** Anthropic's own figure: users approve 93% of permission prompts, and stop reading them [A11]. Operator "frequently asked users for confirmation" [O19]. Watch mode requires the user to keep looking. One Hacker News description: "a lazy babysitter" `[unverified]` [R1].
6. **Live view quality.** Chrome screencast gives 4 to 12 fps, varies with page complexity and cannot show native dialogs or permission prompts [S2]. ChatGPT agent's embedded browser was low resolution [O3]. Manus's Computer panel froze on a page [U5].
7. **Bot walls and logins.** Frequent CAPTCHA blocks [U5]; cloud IPs trigger extra verification [U1]; "identified as bot traffic" even with a human driving [C1]; sites blocking automated browsers [O5]. Manus was criticised for not asking for help when blocked [U5].
8. **Cost and limits.** Browser automation "eats through your usage limits" [A12]; daily task caps [G1]; credits not refunded on cancel [K1].
9. **Overlay cost.** The Claude in Chrome glow animation at about 50% CPU [A6].
10. **Product instability.** Operator, ChatGPT agent, Atlas and Mariner were all withdrawn within 7 to 17 months; ChatGPT agent went "with no meaningful advance notice" [O4].

---

## 7. Accessibility and motion

Vendors say very little. What I found:

- No vendor statement on `prefers-reduced-motion`, screen-reader announcements of agent state, or keyboard operation of approval cards. Not found for any product in scope.
- Browser Use documents an accessible read-only embed: `inert` wrapper, `tabindex="-1"`, a `title` on the iframe [BU2].
- Browserbase: mobile keyboards are not officially supported in the live view [B1].
- Steel: light and dark theme parameter [S1]. Hermes: a large-type theme and font override [H1].
- Motion cost: the animated glow in Claude in Chrome repainted every frame [A6]. Atlas's sparkle overlay drew a negative comment [O14].
- Signalling by colour alone is common (tab group colour, red flashing tab, coloured timeline ticks). No vendor describes a non-colour fallback.
- Agents themselves lean on the accessibility tree (Atlas [R3] `[press]`, Hermes [H2]), and Steel's trace drawer shows each element's role and accessible name [S3].

This is a gap in the market rather than a pattern to copy.

---

## 8. Implications for the prototype (my inference, not evidence)

- The existing set (task panel, live view with URL bar, highlight and caption overlays, timeline with screenshots, result card, approve/deny dialogs) matches what Skyvern, Steel and Manus ship. The missing pieces relative to those products are: an autonomy mode selector, a plan card, an explicit handoff card with reason, a takeover toolbar with its own state, a secure sign-in form, replay, and a multi-run list.
- Approve/deny as a two-button modal is thinner than what ships. Products offer once, always for this site, and deny, and keep a separate, non-removable gate for consequential actions. A card pinned in the timeline, with a screenshot crop and the reason, fits the evidence better than a modal.
- CDP screencast is the transport Steel abandoned for latency and for not showing native dialogs [S2]. If the prototype keeps it, the spec should say what the user sees when the stream is stale and how native dialogs are surfaced.
- Sentence-style timeline rows with collapsed typing and idle dividers [S3], and a caption with elapsed time [U6], address the "unclear what the agent is doing" complaint most directly.
- Accessibility and reduced motion are unaddressed by every vendor reviewed, so the spec has to define them without a reference product.

Open questions the evidence does not settle: whether users prefer plan approval or per-site prompts; how long approval and handoff timeouts should be for consumer use (the only numbers are Cloudflare's 2 to 30 minutes [C1]); whether mid-run steering should interrupt the current action or queue behind it.

---

## 9. Sources

**Anthropic**

- [A1] https://support.claude.com/en/articles/12902446-claude-in-chrome-permissions-guide
- [A2] https://support.claude.com/en/articles/12012173-getting-started-with-claude-for-chrome
- [A3] https://support.claude.com/en/articles/12902428-using-claude-for-chrome-safely
- [A4] https://claude.com/blog/claude-for-chrome
- [A5] https://claude.com/claude-in-chrome
- [A6] https://github.com/anthropics/claude-code/issues/20070
- [A7] https://support.claude.com/en/articles/16607400-use-the-built-in-browser-in-claude-cowork
- [A8] https://claude.com/blog/cowork-built-in-browser
- [A9] https://support.claude.com/en/articles/16635803-set-up-browser-use-in-claude-cowork-for-team-and-enterprise-plans
- [A10] https://support.claude.com/en/articles/14128542-let-claude-use-your-computer-in-cowork
- [A11] https://anthropic.com/engineering/claude-code-auto-mode
- [A12] https://aitoolanalysis.com/claude-in-chrome-review/ `[press]`
- [A13] https://aitoolsreview.co.uk/insights/claude-cowork-browser `[press]`
- [A14] https://www.explainx.ai/blog/claude-cowork-built-in-browser-august-2026 `[press]`

**OpenAI**

- [O1] https://help.openai.com/en/articles/11752874-chatgpt-agent `[excerpt]`
- [O2] https://openai.com/index/introducing-chatgpt-agent/ `[excerpt]`
- [O3] https://www.nngroup.com/articles/impressions-chatgpt-agent/ `[press]`
- [O4] https://community.openai.com/t/agent-mode-was-removed-with-no-real-replacement/1389601
- [O5] https://learn.chatgpt.com/docs/browser
- [O6] https://learn.chatgpt.com/docs/enterprise/chatgpt-work-overview
- [O7] https://help.openai.com/en/articles/20001280-using-cloud-browser-in-chatgpt `[excerpt]`
- [O8] https://github.com/openai/codex/issues/39295
- [O9] https://dev.to/alifar/chatgpt-work-adds-secure-website-sign-ins-for-authenticated-browser-automation-39h6 `[press]`
- [O10] https://chatgptaihub.com/chatgpt-work-cloud-browser-signed-in-websites-secure-login-permissions-confirmation-session-cleanup/ `[press]`
- [O11] https://learn.chatgpt.com/docs/chrome-extension
- [O12] https://jxnl.co/writing/2026/06/16/three-ways-codex-can-use-a-computer/ `[press]`
- [O13] https://codex.danielvaughan.com/2026/05/11/codex-chrome-extension-parallel-browser-workflows-devtools-tab-groups/ `[press]`
- [O14] https://simonwillison.net/2025/Oct/21/introducing-chatgpt-atlas/ `[press]`
- [O15] https://help.openai.com/en/articles/12628199-chatgpt-atlas-agent-mode `[excerpt]`
- [O16] https://allthings.how/chatgpt-atlas-agent-mode-macos-setup-controls-workflows/ `[press]`
- [O17] https://en.wikipedia.org/wiki/ChatGPT_Atlas
- [O18] https://readwise.io/reader/shared/01jjb1jaekf0gtmk3egshfe6dm (mirror of https://openai.com/index/introducing-operator/)
- [O19] https://simonwillison.net/2025/Jan/23/introducing-operator/ `[press]`
- [O20] https://en.wikipedia.org/wiki/OpenAI_Operator
- [O21] https://thejusgrow.com/chatgpt-work-explained/ `[press]`
- [O23] https://www.eesel.ai/blog/chatgpt-atlas-reviews `[press]` `[unverified]` (secondary citation of The Verge and WSJ timings)

**Perplexity**

- [P1] https://techcrunch.com/2025/10/02/perplexitys-comet-ai-browser-now-free-max-users-get-new-background-assistant/ `[press]`
- [P2] https://www.perplexity.ai/hub/blog/comet-assistant-puts-you-in-control `[excerpt]`
- [P3] https://www.perplexity.ai/help-center/en/articles/13531023-managing-comet-assistant-permissions `[excerpt]`
- [P4] https://labs.zenity.io/post/perplexity-comet-a-reversing-story `[press]`
- [P5] https://www.eesel.ai/blog/perplexity-comet-reviews `[press]`

**Google**

- [G1] https://support.google.com/chrome/answer/16821166?hl=en
- [G2] https://blog.google/products-and-platforms/products/chrome/gemini-3-auto-browse/
- [G3] https://9to5google.com/2026/01/28/chrome-gemini-auto-browse/ `[press]`
- [G4] https://9to5google.com/2026/05/12/gemini-chrome-android/ `[press]`
- [G5] https://blog.imseankim.com/chrome-auto-browse-gemini-agentic-hotel-form-fill-google-io-2026/ `[press]`
- [G6] https://www.theregister.com/2026/01/29/chrome_gemini_pane/ `[press]`
- [G7] https://support.google.com/gemini/answer/16596215
- [G8] https://www.androidheadlines.com/2026/05/google-shuts-down-project-mariner-ai-agent.html `[press]`

**Microsoft**

- [M1] https://support.microsoft.com/en-us/topic/copilot-actions-in-edge-5ed5e17e-42df-40a3-984a-20420eba86e2
- [M2] https://blogs.windows.com/msedgedev/2026/05/20/new-in-edge-for-business-ai-for-work-safe-from-day-one/
- [M3] https://tech.yahoo.com/ai/copilot/articles/put-microsofts-ai-browser-test-120000768.html `[press]` (PCMag, 2025-10-29)
- [M4] https://piunikaweb.com/2026/07/03/microsoft-new-toggle-copilot-cowork/ `[press]`

**Opera**

- [N1] https://blogs.opera.com/news/2025/09/opera-neon-agentic-ai-browser-release/
- [N2] https://www.remio.ai/post/opera-neon-review-the-confusing-future-of-ai-browsers `[press]` (relays The Verge)
- [N3] https://www.ghacks.net/2025/09/30/opera-neon-ai-agentic-browser-released-in-early-access/ `[press]`
- [N4] https://www.cloudwards.net/opera-neon-review/ `[press]` `[excerpt]`

**Manus**

- [U1] https://manus.im/docs/features/cloud-browser
- [U2] https://manus.im/docs/features/browser-operator
- [U3] https://manus.im/blog/manus-browser-operator
- [U4] https://help.manus.im/en/articles/11711218-how-can-i-take-over-manus-browser-or-vs-code
- [U5] https://www.technologyreview.com/2025/03/11/1113133/manus-ai-review/ `[press]`
- [U6] https://aiuxplayground.com/teardowns/manus/output `[press]`
- [U7] https://workos.com/blog/introducing-manus-the-general-ai-agent `[press]`

**Browser infrastructure**

- [B1] https://docs.browserbase.com/features/session-live-view
- [B2] https://docs.browserbase.com/features/session-replay
- [B3] https://docs.browserbase.com/features/observability
- [B4] https://browserbase.com/blog/introducing-director
- [BU1] https://docs.browser-use.com/tips/live-view/human-takeover
- [BU2] https://docs.browser-use.com/cloud/browser/live-preview
- [BU3] https://docs.browser-use.com/cloud/api-v4/get-shared-session-recording `[excerpt]`
- [S1] https://docs.steel.dev/overview/sessions-api/embed-sessions/live-sessions
- [S2] https://steel.dev/blog/webrtc
- [S3] https://steel.dev/blog/agent-traces
- [S4] https://steel.dev/blog/agent-logs
- [K1] https://www.skyvern.com/docs/cloud/getting-started/monitor-a-run
- [K2] https://www.skyvern.com/docs/cloud/viewing-results/run-details
- [K3] https://www.skyvern.com/docs/cloud/getting-started/overview
- [K4] https://skyvern.com/blog/skyvern-changelog-july-2026/
- [W1] https://docs.aws.amazon.com/nova-act/latest/userguide/hitl.html
- [W2] https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-session-recording.html
- [C1] https://developers.cloudflare.com/browser-run/features/human-in-the-loop/
- [C2] https://developers.cloudflare.com/browser-run/features/live-view/
- [C3] https://developers.cloudflare.com/changelog/post/2026-04-15-br-observability/

**Open-source agents**

- [H1] https://hermes-agent.nousresearch.com/docs/user-guide/features/web-dashboard
- [H2] https://hermes-agent.nousresearch.com/docs/user-guide/features/browser
- [X1] https://docs.openclaw.ai/tools/browser
- [X2] https://docs.openclaw.ai/tools/exec-approvals
- [X3] https://docs.openclaw.ai/tools/browser-login `[excerpt]`
- [X4] https://open-claw.bot/docs/tools/chrome-extension/ `[excerpt]`

**General**

- [R1] https://news.ycombinator.com/item?id=46934404 `[unverified]` (quote seen only in a search excerpt)
- [R3] https://adrianroselli.com/2025/10/openai-aria-and-seo-making-the-web-worse.html `[press]`

### Pages that could not be read directly

help.openai.com (all articles), openai.com/index pages, perplexity.ai help centre and blog, cybernews.com, notebookcheck.net, cloudwards.net and x.com returned HTTP 402/403. Claims from them are marked `[excerpt]` or replaced with other sources. If the spec depends on exact OpenAI or Perplexity strings, read those pages in a browser.
