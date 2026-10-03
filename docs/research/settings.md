# Claude settings inventory: web app, desktop app, Claude in Chrome, org admin

As documented on 2026-10-03. Input to the settings design in `docs/bap-browser-spec.md`, section 10.2.

## How to read this

- **Evidence base:** official documentation only. No signed-in settings screen was inspected, so anything the docs do not mention is absent here or listed under "Not verified".
- **Source column:** IDs (H = Help Center, P = Privacy Center, D = docs, B = blog) resolve to full URLs in section 7.
- **Confidence:** every row is "Official doc" unless marked otherwise. No row rests on a third-party source.
- **The product is mid-transition:**
  - "Claude Cowork and chat are one Claude" is rolling out to Pro/Max; in that experience the permission selector offers only Auto and Manual (default) (H43).
  - On 2026-10-06 the "Only on your computer" option is removed for Pro/Max (H11, H12).

## 1. Table A: Claude web app (claude.ai) settings

| Section | Setting (as shown) | What it controls | Values / default | Who | Source |
|---|---|---|---|---|---|
| Settings > General | Full name | Display name | Free text, "Save changes"; default not stated | User | H39 |
| Settings > General | Instructions for Claude | Account-wide instructions applied to all conversations; absorbs Cowork "Global instructions" in the new experience | Free text; default not stated | User | H23, H43 |
| Settings > General > Voice | Voice settings (voice choice) | Voice used in voice mode, with preview | Preset voices; default not stated | User | H38 |
| Settings > General > Voice | Language | Voice-mode language, separate from display language | Language list; default not stated | User | H25, H38 |
| Profile menu | Language | Interface language | 11 languages (English, French, German, Hindi, Indonesian, Italian, Japanese, Korean, Portuguese (Brazilian), Spanish (Latin America), Spanish (Spain)) | User | H25 |
| Settings > Appearance | Color mode | Theme | Light / Match System / Dark; default not stated | User | H24 |
| Settings > Appearance | Chat font | Chat typeface | Default / Match System / Dyslexic Friendly | User | H24 |
| Settings > Account | Active sessions | Lists device and browser, location, updated time, current-session badge; per-session "Terminate" or "Log out" | n/a | User | H35 |
| Settings > Account | Log Out (all devices) | Signs out web, mobile and desktop everywhere | Web session lasts 28 days, refreshed on activity | User | H42 |
| Settings > Account | Delete account | Deletes the account | n/a | User | H49 |
| Settings > Account | Close your personal account | Starts migration of a personal account into an org | n/a | User | H62 |
| Settings > Account | Organization ID; Primary Owner; Program verifications | Read-only identifiers; verification discounts | n/a | User (view) | H63, H30, H61 |
| Settings > Privacy | Help improve our AI models | Whether chats and coding sessions are used for model training (consumer plans) | Toggle; default not stated | User | P1, H12 |
| Settings > Privacy | Export data | Emails a download link for chats and account data | Link expires in 24 h; Free/Pro/Max only; web or desktop, not mobile | User | H41 |
| Settings > Privacy | Shared chats > Manage | List of shared chat links, with "Unshare" | n/a | User (Free/Pro/Max) | H48, H58 |
| "Privacy dashboard" | Location data for product features | Use of IP-derived coarse location for features such as web search | Can be disabled; setting name and default not stated | User | P2 |
| Settings > Billing | Payment method, billing address, "Use a different name on invoices", Upgrade plan, Cancel | Subscription and invoicing | n/a | User (owner on org plans) | H57 |
| Settings > Usage | Usage bars; reset time; usage credits; usage bundles | Shows five-hour and weekly limit consumption; enable or disable usage credits | Usage credits can be disabled; default not stated | User | H52, H60 |
| Settings > Capabilities | Code execution and file creation (also written "Cloud code execution and file creation") | Sandboxed code and file creation; required for artifacts | On by default for Free/Pro/Max | User; owner on Team/Enterprise | H34, H46 |
| Settings > Capabilities | Allow network egress | Sandbox internet access | Free/Pro/Max: network access enabled by default | User; owner on Team/Enterprise | H34 |
| Settings > Capabilities | AI-powered artifacts | Lets legacy artifacts call Claude | Toggle; default not stated | User | H46 |
| Settings > Capabilities | Switch models when a message is flagged | Automatic fallback to an older model on a safety flag | On by default | User | H40 |
| Settings > Memory | Search and reference chats | Claude may search past chats | On by default once rolled out (paid plans) | User | H21 |
| Settings > Memory | Generate memory from chats | Memory across chats and cloud Cowork; turning off offers "Pause memory" or "Reset memory" | On by default for Free/Pro/Max; off per member on Team/Enterprise until the owner enables and the member opts in | User; owner gates | H21 |
| Settings > Memory | Include sensitive topics in memory | Saving health, beliefs and similar topics | Off by default; some data is never saved (government IDs, financial account numbers, criminal history, immigration status) | User | H21 |
| Settings > Memory | Topics (view, edit, Delete); "Tell Claude what to change or remove"; Start import | Inspect and edit what is remembered; import memory | n/a | User | H21, H59 |
| Settings > Claude Code | Authorization tokens | Remove a token to log Claude Code out | n/a | User | H42 |
| Settings > Claude Code | Sharing settings | Require repository access for recipients; hide your name on shared sessions | Not stated | User | D6 |
| Settings > Claude Code | Default transcript view | Normal / Thinking / Verbose for new sessions; syncs with desktop | Default not stated | User | D10 |
| Settings > Claude Code | Usage analytics | View of Claude Code usage | n/a | User | H53 |
| Settings > Cowork (surface not stated) | Global instructions (Edit) | Standing instructions for every Cowork session | Free text | User | H11 |
| Settings > Time and focus | Break reminders | Nudge after a chosen amount of daily time | Dropdowns; off until set; beta on Free/Pro/Max | User | H27 |
| Settings > Time and focus | Quiet hours | Reminder when opening Claude in chosen windows | Days of week plus start and end time; off until set | User | H27 |
| Settings > Reflect | Monthly recap | Usage recap, generated only when the page is opened; can be turned off | Beta on Free/Pro/Max; needs memory on | User | H50, H45 |
| Settings > Design systems | Design systems | Manage Claude Design systems | n/a | User | H51 |
| Settings > Analytics | Analytics | Org usage analytics for members granted access | n/a | Role-gated | H54, H29 |
| Customize > Connectors | Add ("+"), Connect / Install, disconnect | Which services Claude can reach | n/a | User; owner must enable first on Team/Enterprise | H20 |
| Customize > Connectors | Tool permissions (per category or tool) | Approval level for a connector's tools | Always allow / Needs approval / Blocked; personal menu shows Always allow / Ask / Never, capped by org policy | User within the org ceiling | H20, H28 |
| Customize > Connectors | Custom connector (Add > Custom > Web) | Name, remote MCP URL, Authentication, OAuth client, Request headers | Authentication: "Sign in now" / "Sign in when needed" / "No sign in"; Free plan limited to one | User | H20 |
| Customize > Skills | Skill toggles, upload, "Record your screen", Browse skills | Which skills are active | Directory skills enabled by default once added | User | H55 |
| Customize > Plugins | Discover tab; Shared with you | Install plugins | Org may set Installed by default / Available / Required / Not available | User; owner | H56, H10 |
| In chat (not Settings) | Model, Effort, Thinking | Model and reasoning effort per chat | Effort: Low / Medium / High / Extra high / Max; "Default" marked per model | User; admin may cap | H26 |
| In chat "+" menu | Web search | Per-chat web search toggle (absent in the new experience) | Not stated | User; owner enables on Team/Enterprise | H33 |
| In chat "+" menu | Connectors > Tool access | How connectors load | Auto (default) / Always available / On demand | User | H47, H20 |
| In chat "+" menu | Memory | Turn memory off for one chat or task; fixed once the first message is sent | On when account memory is on | User | H21 |
| In chat | Incognito chat (ghost icon) | Chat not saved to history or memory; retained 30 days | Off | User | H22 |
| In chat | Permission mode selector | When Claude asks before acting on tasks | Manual / Auto / Skip; new experience: Auto and Manual (default) | User; admin can remove Auto | H11, H43 |

Naming note: docs use both "Customize > Connectors" (H20) and "Settings > Connectors" (H18, H19, D2). The 2026-09-17 desktop release moved Skills, Plugins and Connectors to a full Customize page and moved Memory under Settings (D10).

## 2. Table B: Claude desktop app settings (Windows and macOS)

| Section | Setting (as shown) | What it controls | Values / default | Who | Also on web? | Source |
|---|---|---|---|---|---|---|
| Settings > General (Desktop app) | Enable computer use (also written "Computer use") | Lets Claude click, type and see the screen | Off by default; Pro/Max only; macOS also needs Accessibility and Screen Recording; changelog says macOS 14 or later | User | No | H8, D2, D10 |
| Settings > General (Desktop app) | When Claude requests access to an app | Background work versus taking over the screen | "Full control" named; background is default on macOS 15+ | User | No | H8 |
| Settings > General (Desktop app) | Denied apps | Apps rejected without a prompt | User list; default contents not stated | User | No | D2, H8 |
| Settings > General (Desktop app) | Unhide apps when Claude finishes | Restores windows hidden during computer use | On by default | User | No | D2 |
| Per-app prompt (computer use) | Allow for this session / Deny | Per-application approval | Lasts the session, or 30 minutes in Dispatch-spawned sessions | User | No | D2, D3 |
| Per-app tiers (fixed) | View only / Click only / Full control | Control level by app category | Browsers and trading platforms: view only. Terminals and IDEs: click only. Everything else: full control. Not changeable; extra warning for terminals, Finder/File Explorer, System Settings | Fixed | No | D2, D3 |
| Settings > General (Desktop app) | Quick access shortcut | Global hotkey for Quick Entry | Double-tap Option (default) / Option + Space / Custom; article covers macOS only | User | No | H15 |
| Settings > General (Desktop app) | Voice shortcut | Dictation hotkey | Caps Lock / custom / disabled; off by default. The 2026-09-17 release says this shortcut "could not work" and no longer opens the dictation bar | User | No | H15, D10 |
| Settings > Desktop app > General | Keep computer awake | Prevents idle sleep so scheduled tasks run | Default not stated | User; admin can hide | No | D4, D8 |
| Settings > General | Only on your computer | Run Cowork tasks locally instead of in the cloud | Removed for Pro/Max on 2026-10-06 | User | No | H11, H12 |
| Settings > Cowork | Preferred browser | Which browser Claude uses for web tasks | "Built-in browser" or "Chrome (Claude in Chrome)"; default is Claude in Chrome if already used, otherwise built-in | User; owner controls availability | Applies to web and mobile sessions, set in desktop | H6, H7 |
| Built-in browser (first open) | Import cookies ("Stay signed in to your sites by importing cookies from your browser") | Brings existing logins into the built-in browser | Site by site; banking, email and SSO unchecked by default; from Chrome, Edge, Firefox on macOS, Firefox only on Windows and Linux | User | No | H6 |
| Built-in browser | Site approval card | First action on a site | Allow once / Always allow (saved on device, revocable in Settings) / Deny; each site and subdomain separately | User | No | D2, D7 |
| Built-in browser pane menu | Clear browsing data; Keep cookies | Clears sign-ins (Cowork); cookie persistence in Code sessions | Keep cookies: Shared / Per session; Code sessions otherwise clear on quit | User | No | D7 (third-party-inference doc) |
| Settings > Claude Code | Browser on/off; clear saved session data | Turns the Code tab Browser off; clears saved sessions | Not stated | User | No | D2 |
| Settings > Claude Code | Allow bypass permissions mode | Enables "Bypass permissions" mode | Pro/Max only; on Team/Enterprise org policy decides | User; admin | No | D2 |
| Settings > Claude Code | Worktree location; branch prefix | Where session worktrees live | Default `<project-root>/.claude/worktrees/` | User | No | D2 |
| Settings > Claude Code | Auto-archive after PR merge or close | Archives finished sessions | Off unless turned on | User | No | D2 |
| Settings > Claude Code | Connect new sessions to Remote Control | Auto-enables remote control from phone or web | Not stated | User; admin | No | D5 |
| Settings > Claude Code | Keep computer awake while Claude works; Keep awake on battery power | Stops idle sleep during Code work | Not stated | User; admin can hide | No | D10 |
| Settings > Claude Code | Default output style | Default Claude Code output style | Not stated | User | Not stated | D10 |
| Code tab prompt area | Permission mode | Autonomy for Code sessions | Manual / Accept edits / Plan / Auto / Bypass permissions; remembered per folder | User; admin can remove Auto and Bypass | Partly (cloud sessions: Accept edits, Plan, Auto) | D2 |
| Settings > Extensions | Browse extensions, Install, per-extension settings | Local MCP servers as one-click packages; secrets stored in OS keychain | Directory extensions auto-update by default | User; admin allowlist | No | H17, H14 |
| Settings > Extensions > Advanced settings | Extension Developer > "Install Extension…" | Install a custom .mcpb file | n/a | User; admin can block | No | H17 |
| Developer (Desktop app) | MCP server status and logs | Connection status of local MCP servers | n/a | User; hidden when admin disables local MCP | No | H17, D10 |
| Settings > Connectors | Claude in Chrome > Configure > toggle | Connects desktop to the extension | Per conversation it is disabled by default and must be enabled in the Connectors drop-down | User; admin | No | H3, H5 |
| Settings (location not stated) | "Allow all browser actions" switch | Blanket approval for Claude in Chrome actions | Exists per changelog; removed from permission cards 2026-08-17 | User | No | D10 |
| Settings > Connectors | 1Password > Connect | Credential fill without Claude seeing passwords | macOS beta; off by default for Team/Enterprise | User; owner | No | H19 |
| Settings | Storage folder; Trusted folders | Where Cowork saved work; folders Claude may access | n/a | User; admin can restrict folders | No | H43 |
| Cowork | Folder instructions | Per-folder context | n/a | User | No | H11 |
| Dispatch setup | Give Claude access to your files; keep your computer awake | Setup toggles for phone-to-desktop tasks | Not stated; Dispatch closed to new users | User | No | H31 |
| Scheduled > New task | Task name, prompt, approval mode, frequency, model, folder | Recurring tasks | Hourly / daily / weekly / weekdays / manual; Claude-created tasks default to "Automatically approve" where the org allows | User | Yes | H32, D10 |
| OS notifications | (no named setting) | Notification when a Code session finishes; phone push when a task finishes or needs approval | macOS permission requested at first notification | User (OS level) | Phone push applies to cloud sessions | D2, D10, H12 |

## 3. Table C: Claude in Chrome extension settings and permission model

| Area | Setting / behaviour (as shown) | What it controls | Values / default | Who | Source |
|---|---|---|---|---|---|
| Chat input drop-down | Permission mode | When Claude asks before acting | "Manually approve" (formerly "Ask before acting") / "Automatically approve" / "Skip all approvals" (formerly "Act without asking"). Cowork side panel defaults to Automatically approve and remembers your choice. Classic side panel default not stated | User; admin can remove Auto | H1, H3, H10 |
| Classic side panel, Manual | Plan approval | Claude proposes the sites and approach before starting | "Approve plan" / "Make changes"; Claude uses only the listed sites | User | H1 |
| Cowork side panel, Manual | Per-action prompt | Approval per action | "Allow all for this website" / "Allow this time only" / "Deny" | User | H1 |
| Any panel | "New permissions required" prompt | Sites that need approval for every action | "Allow this action" / "Always allow actions on this site" / "Decline" | User | H1 |
| Automatically approve | Automatic action screening | Each action is checked for exfiltration and prompt injection; unsafe ones blocked; reverts to per-step asking after repeated blocks | Uses more of the usage limit | System | H1, H4 |
| Protected actions | Always ask, even with "Always allow" on the site | Downloading a file; entering potentially sensitive information; granting authorizations | Fixed | System | H1 |
| Explicit permission in any mode | n/a | Modifying permission settings; granting authorizations; entering potentially sensitive information | Fixed | System | H1 |
| Prohibited actions | n/a | Purchases or financial transactions; creating accounts; handling card or ID data; downloads from untrusted sources; permanent deletions; investment advice; financial trades; modifying system files; completing instructions from emails or web content. Also bypassing captchas and scraping facial images | Fixed | System | H1, H4 |
| Extension settings (three dots > "Extension settings") | Permissions page: "Your approved sites" | Review always-allowed sites, revoke, see permission history | n/a | User | H1 |
| Blocked sites | Default blocked categories | Sites Claude cannot use | Sources disagree: H4 lists adult and pirated content and says Claude asks before financial sites; H5 lists financial services, banking, investment, crypto exchanges, adult, pirated; B1 lists financial services, adult, pirated | System | H4, H5, B1 |
| Site safety check | n/a | Checks public URLs against Anthropic's list | Logs account ID, IP, timestamp, OS and Chrome version; no URL or page content | System | D7 |
| What Claude sees | Screenshots of the tabs it works in | Anything visible is captured into the conversation; cannot be filtered | Sessions saved to history in the Cowork side panel | n/a | H4, H3 |
| Sign-in handling | Uses the user's existing Chrome logins | Claude acts with accounts already signed in | Via Claude Code it pauses for login pages and CAPTCHAs | User | H6, D1 |
| Sign-in handling | 1Password for Claude | 1Password fills credentials; Claude never sees the password or one-time code | Approve / swap / deny per request with biometrics; scoped to the task; macOS beta | User; owner | H19, H3 |
| Shortcuts | Save prompt as shortcut; "/" to run; edit or delete in extension settings | Reusable prompts | n/a | User | H3 |
| Record a workflow | Record icon | Teach by demonstration, saved as a shortcut | Classic side panel only | User | H3 |
| Scheduled tasks | Clock icon | Run shortcuts on a schedule | Daily / weekly / monthly / annually | User | H3 |
| Model selection | Model picker | Model used | "Available on all public models"; current default not stated | User | H3, H45 |
| Notifications | Enable notifications | Alerts when Claude needs permission or finishes; optional sound | Opt-in ("Enable notifications"); default not stated | User | H3 |
| Tab group | Claude's tab group | Claude's tabs sit in a separate coloured group; dragging a tab in grants access | n/a | User | H3, D1 |
| Side panel menu | "Switch back to classic" | Return to the previous side panel | n/a | User | H3 |
| Dictation | Microphone permission in extension settings | Dictation in the side panel | Allow once | User | D10 |
| Install permissions | Chrome permissions | sidePanel, storage, scripting, debugger, tabGroups, tabs, alarms, notifications, system.display, webNavigation, declarativeNetRequestWithHostAccess, offscreen, nativeMessaging, downloads, unlimitedStorage | Required | User at install | H3 |
| Claude Code | `--chrome`, `/chrome`, "Enabled by default" | Connect, check status, manage permissions, reconnect, select browser | Off by default; site permissions inherited from the extension | User; admin can block | D1 |
| Claude Code | "Claude in Chrome wants to" dialog | Per-action approval, with allow-all-on-this-site-for-the-session | n/a | User | D1 |
| Supported browsers | n/a | Where it runs | Sources disagree: H3 says Chrome only; D1 and D7 say Chrome and Edge, D1 adds other Chromium browsers | n/a | H3, D1, D7 |

## 4. Table D: Org admin controls (Team / Enterprise)

| Where | Control (as shown) | What it governs | Values / default | Who | Source |
|---|---|---|---|---|---|
| Organization settings > Claude in Chrome | Enable for your team | Whether members can use the extension | Team: on. Enterprise: off, switching to on from 2026-09-10 unless already disabled | Owner / Primary Owner | H2, H7 |
| Organization settings > Claude in Chrome | Allowlist / Blocklist ("Add websites") | Sites Claude may navigate to and act on; one list covers the extension and the built-in browser | All-except-blocked or only-allowed; a blocked URL typed by the user still loads, with a banner and Claude's tools disabled | Owner | H2, D7 |
| Organization settings > Claude in Chrome | Password managers | 1Password for Claude | Off by default | Owner | H19, H2 |
| Organization settings > Roles | "Claude for Chrome" capability | Per-role access, separate from Cowork | Must be granted for Custom-role members (Enterprise) | Owner or Identity & Access manager | H28, H2 |
| Chrome enterprise policy | `forceLoginOrgUUID` | Restricts which org the extension can sign in to | Not set by default | IT admin | H2 |
| Chrome management | Managed deployment | Push or limit installs via Google Workspace or MDM | n/a | IT admin | H2 |
| Organization settings > Cowork | Enable for your organization | Cowork availability | On by default | Owner | H10 |
| Organization settings > Cowork | Run Cowork in the cloud | Cloud sessions | Team: on. Enterprise: off, plus a role grant | Owner | H10 |
| Organization settings > Cowork | Built-in browser | Built-in browser availability | Team: on. Enterprise: off, on by default from 2026-09-10 unless turned off | Owner | H7, H10 |
| Organization settings > Cowork > Permissions | Allow "Automatically approve" mode | Whether Auto appears in members' mode selector | On by default | Owner | H10 |
| Organization settings > Cowork > Permissions | Allow "Always allow" for connector tools | Whether members can skip per-task approval for write-capable tools | Off by default; roles cannot override | Owner | H10, H28 |
| Organization settings (cloud sessions) | Trusted-device enrollment and recent sign-in; no-prompt sessions | Extra gates on cloud sessions | Defaults not stated | Owner | H44 |
| Organization settings > Capabilities | Web search; Code execution and file creation; network egress; Memory | Org-wide capability switches | Egress options: off / package managers only / plus specific domains / all domains; Enterprise egress off by default; Team default stated inconsistently in H34 | Owner | H33, H34, H21 |
| Organization settings > Connectors | Add to your team; per-tool policy | Which connectors exist and the ceiling for each tool | Always allow / Needs approval / Blocked; members cannot override | Owner | H20, H28 |
| Organization settings > Connectors > Desktop | Allowlist toggle; Browse extensions; Add custom extension | Which desktop extensions members may install | Off by default (all extensions allowed until enabled); enabling force-deletes non-listed installs | Owner | H16 |
| Organization settings > Roles | Custom roles | Per-group capabilities, connector and tool levels, model access | Most restrictive of platform, org, role, user wins; role grants are additive | Owner | H28, H29 |
| Organization settings > Organization and access | Shortened session length | Forces re-login | 1 / 7 / 14 / 28 days; off by default | Admin and above (Enterprise) | H36 |
| MDM / Group Policy | Desktop policy keys | allowedWorkspaceFolders, disableAutoUpdates, autoUpdaterEnforcementHours, effortLevel, forceLoginOrgUUID, isClaudeCodeForDesktopEnabled, isDesktopExtensionEnabled, isDesktopExtensionDirectoryEnabled, isLocalDevMcpEnabled, secureVmFeaturesEnabled | Feature keys default true; machine-level beats user-level; setting isLocalDevMcpEnabled false also cuts the desktop-to-Chrome link | IT admin | H13, H2 |
| Claude Code admin console | Code in the desktop; Code in the web; Remote Control; Disable Bypass permissions mode | Claude Code surfaces and the bypass mode | Not stated | Owner | D2 |
| Claude Code managed settings | `disableAutoMode`, `permissions.disableBypassPermissionsMode`, `browserExternalPageTools`, `disableBrowserExternalNavigation`, `deniedMcpServers` | Remove Auto or Bypass; stop Claude reading or acting on external pages; block external browsing; block the Chrome integration | Not set by default | IT admin | D2, D1 |
| Claude Desktop on third-party inference | `builtinBrowserEnabled`, `builtinBrowserDefaultDomainPolicy`, `builtinBrowserAllowedDomains`, `builtinBrowserBlockedDomains`, `mcpPersistentAlwaysAllowEnabled`, `autoModeEnabled`, `disableBypassPermissionsMode`, `keepAwakeEnabled`, `scheduledTasksEnabled` | Same controls for third-party deployments | Browser off by default; domain policy `allow`; persistent approvals on | IT admin | D7, D8 |
| Plan limits | Computer use | Not available on Team or Enterprise at all | n/a | n/a | H8, D2 |
| Plan limits | Zero data retention; HIPAA | ZDR not supported for Claude in Chrome; not available to HIPAA orgs | n/a | n/a | H2, H4 |

## 5. Differences

**Desktop has, web does not (all because they need the local machine):**

- Computer use, with per-app approval, fixed app tiers, Denied apps and Unhide apps.
- The built-in browser, cookie import, on-device site approvals and Clear browsing data.
- Preferred browser choice. It is set in the desktop app, although it also governs web and mobile sessions.
- Local folders (Trusted folders, Storage folder, folder instructions).
- Desktop extensions, local MCP servers and the Developer section.
- Quick Entry and voice shortcuts, which need OS hotkeys and macOS permissions.
- Keep-awake settings.
- Local Claude Code settings (bypass permissions, worktree location, Browser toggle).
- The Claude in Chrome connector bridge and 1Password integration.
- Device policies through MDM or the Windows registry.

**Web has, desktop does not:**

- Nothing documented as web-only apart from "log out of all sessions", which H42 describes on the web version.
- Account-level settings (General, Appearance, Privacy, Memory, Capabilities, Billing, Usage) are documented as shared between web and desktop.
- Web and mobile sessions reach local files, browser use and computer use only through an open desktop app (H12).

## 6. Not verified

- **Notification settings:** no "Settings > Notifications" page appears in any of the 232 Help Center articles scanned. Docs describe notifications as behaviour, not a settings screen.
- **Start at login, menu-bar or tray toggles:** not documented. The changelog mentions a menu bar usage menu and a Linux tray icon, but no setting for them.
- **Quick Entry on Windows:** the only article (March 2026) says macOS only; current Windows behaviour is not documented.
- **Extension settings pages other than "Permissions":** tab names, where the notification toggle sits, the default model and the default keyboard shortcut are not in official docs. Third-party pages opened did not settle this.
- **Classic side panel default permission mode:** not stated.
- **"Allow all browser actions" switch and the list of always-allowed sites in desktop Settings:** existence confirmed, location not stated.
- **Default of "Help improve our AI models"** and the exact name of the location-data setting: not stated.
- **Whether Settings > Cowork exists on the web app:** not stated.
- **Profile fields beyond Full name and Instructions for Claude:** none documented.
- **Blocked categories and supported browsers:** official sources contradict each other (see Table C).
- **Third-party claims not confirmed:** scheduled-task results by email; admin control of extension models.
- **Developer section's "Edit Config" flow:** no page describing it was opened.

A walk through a signed-in account's settings screens (web, desktop, extension) would close most of these gaps.

## 7. Sources opened

Help Center, `https://support.claude.com/en/articles/` + path. The date is the one shown on the page; relative where no absolute date was shown.

- H1 `12902446-claude-in-chrome-permissions-guide` — Claude in Chrome permissions guide — 2026-08-12
- H2 `13065128-claude-in-chrome-admin-controls` — Claude in Chrome admin controls — 2026-09-28
- H3 `12012173-get-started-with-claude-in-chrome` — Get started with Claude in Chrome — 2026-08-26
- H4 `12902428-use-claude-in-chrome-safely` — Use Claude in Chrome safely — 2026-08-12
- H5 `12902405-claude-in-chrome-troubleshooting` — Claude in Chrome troubleshooting — 2026-08-12
- H6 `16607400-use-the-built-in-browser-in-claude-cowork` — Use the built-in browser in Claude Cowork — 2026-09-16
- H7 `16635803-set-up-browser-use-in-claude-cowork-for-team-and-enterprise-plans` — Set up browser use in Claude Cowork for Team and Enterprise plans — "over 2 weeks ago"
- H8 `14128542-let-claude-use-your-computer-in-cowork` — Let Claude use your computer in Cowork — 2026-09-16
- H9 `13364135-use-claude-cowork-safely` — Use Claude Cowork safely — 2026-09-16
- H10 `13455879-use-claude-cowork-on-team-and-enterprise-plans` — Use Claude Cowork on Team and Enterprise plans — 2026-09-25
- H11 `13345190-get-started-with-claude-cowork` — Get started with Claude Cowork — "this week"
- H12 `15520349-use-claude-cowork-on-web-desktop-and-mobile` — Use Claude Cowork on web, desktop, and mobile — "this week"
- H13 `12622667-enterprise-configuration-for-claude-desktop` — Enterprise configuration for Claude Desktop — 2026-09-02
- H14 `10065433-install-claude-desktop` — Install Claude Desktop — "over a week ago"
- H15 `12626668-use-quick-entry-with-claude-desktop-on-mac` — Use quick entry with Claude Desktop on Mac — 2026-03-16
- H16 `12592343-enabling-and-using-the-desktop-extension-allowlist` — Enabling and using the desktop extension allowlist — 2026-03-16
- H17 `10949351-getting-started-with-local-mcp-servers-on-claude-desktop` — Getting Started with Local MCP Servers on Claude Desktop — "over a week ago"
- H18 `11725091-when-to-use-desktop-and-web-connectors` — When to use desktop and web connectors — "over a week ago"
- H19 `15936181-get-started-with-1password-for-claude` — Get started with 1Password for Claude — 2026-07-16
- H20 `11176164-use-connectors-to-extend-claude-s-capabilities` — Use connectors to extend Claude's capabilities — "yesterday"
- H21 `11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context` — Use Claude's chat search and memory — "this week"
- H22 `12260368-use-incognito-chats` — Use incognito chats — "this week"
- H23 `10185728-understanding-claude-s-personalization-features` — Understanding Claude's personalization features — "over 2 weeks ago"
- H24 `8887527-customizing-your-appearance-settings` — Customizing your appearance settings — 2026-03-16
- H25 `10769299-how-to-use-claude-in-your-preferred-language` — How to use Claude in your preferred language — 2026-08-06
- H26 `8664678-change-the-model-effort-and-thinking-settings` — Change the model, effort, and thinking settings — "this week"
- H27 `15672868-set-break-reminders-and-quiet-hours` — Set break reminders and quiet hours — 2026-07-09
- H28 `13930452-manage-custom-roles-on-enterprise-plans` — Manage custom roles on Enterprise plans — "over a week ago"
- H29 `13930458-set-up-role-based-permissions-on-enterprise-plans` — Set up role-based permissions on Enterprise plans — "over 2 weeks ago"
- H30 `9267276-roles-and-permissions` — Roles and permissions — "over a week ago"
- H31 `13947068-assign-tasks-from-anywhere-in-claude-cowork` — Assign tasks from anywhere in Claude Cowork — "over 2 weeks ago"
- H32 `13854387-schedule-recurring-tasks-in-claude-cowork` — Schedule recurring tasks in Claude Cowork — "this week"
- H33 `10684626-enable-and-use-web-search` — Enable and use web search — "this week"
- H34 `12111783-create-and-edit-files-with-claude` — Create and edit files with Claude — 2026-08-06
- H35 `13124001-managing-your-active-sessions` — Managing your active sessions — 2026-03-16
- H36 `13163631-configuring-session-security-settings` — Configuring session security settings — 2026-05-07
- H37 `14503520-available-beta-and-research-preview-features` — Available beta and research preview features — 2026-07-07 (read, not cited)
- H38 `11101966-use-voice-mode` — Use voice mode — "over 2 weeks ago"
- H39 `13325567-account-management-faqs` — Account management FAQs — 2026-08-06
- H40 `17161993-why-claude-switched-models-in-your-conversation-with-sonnet-5-5` — Why Claude switched models in your conversation with Sonnet 5.5 — "this week"
- H41 `9450526-export-your-claude-data` — Export your Claude data — 2026-07-08
- H42 `10310342-how-do-i-log-out-of-all-active-sessions` — How do I log out of all active sessions? — 2026-08-06
- H43 `16761823-claude-cowork-and-chat-are-one-claude` — Claude Cowork and chat are one Claude — "over 2 weeks ago"
- H44 `14479288-claude-cowork-architecture-overview` — Claude Cowork architecture overview — "over 2 weeks ago"
- H45 `12138966-release-notes` — Release notes — "this week" (keyword-filtered read)
- H46 `17153992-what-are-artifacts-and-how-do-i-use-them` — What are artifacts and how do I use them? — "over a week ago" (matching passages only)
- H47 `13730515-manage-claude-s-tool-access` — Manage Claude's tool access — 2026-03-16
- H48 `10593882-share-and-unshare-chats` — Share and unshare chats — 2026-06-15 (matching passages only)
- H49 `9028421-delete-your-claude-account` — Delete your Claude account — 2026-08-19 (matching passages only)

Opened by script; only the sentences naming a settings path were read (dates not captured):

- H50 `15672559-see-your-monthly-recap`
- H51 `14604397-set-up-your-design-system-in-claude-design`
- H52 `9797557-usage-limit-best-practices`
- H53 `12157520-claude-code-usage-analytics`
- H54 `12883420-view-usage-analytics-for-team-and-enterprise-plans`
- H55 `12512180-use-skills-in-claude`
- H56 `13837440-use-plugins-in-claude`
- H57 `8325618-paid-plan-billing-faqs`, `8325617-cancel-your-pro-or-max-subscription`, `12997130-understanding-your-billing-address-and-tax-calculation`
- H58 `16762437-public-links-for-shared-chats`
- H59 `12123587-import-and-export-your-memory-from-claude`
- H60 `12429409-manage-usage-credits-for-paid-claude-plans`
- H61 `16634237-claude-team-plan-for-scientists`
- H62 `9267400-move-your-personal-claude-account-to-a-team-or-enterprise-organization`
- H63 `13198485-enforce-network-level-access-control-with-tenant-restrictions`

Privacy Center:

- P1 https://privacy.claude.com/en/articles/12109829-how-do-i-change-my-model-improvement-privacy-settings — How do I change my model improvement privacy settings? — 2026-08-03
- P2 https://privacy.claude.com/en/articles/11186740-does-claude-use-my-location — Does Claude use my location? — 2026-03-16
- P3 https://privacy.claude.com/en/articles/10023548-how-long-do-you-store-my-data — How long do you store my data? — 2026-07-01 (read, not cited)
- P4 https://privacy.claude.com/en/articles/10030352-what-personal-data-will-be-processed-by-computer-use — What personal data will be processed by Computer use? — 2026-03-16 (API-focused, not cited)

Docs (no page dates shown):

- D1 https://code.claude.com/docs/en/chrome.md — Use Claude Code with Chrome
- D2 https://code.claude.com/docs/en/desktop.md — Desktop application (permission, browser, computer use, Dispatch, connectors and enterprise sections)
- D3 https://code.claude.com/docs/en/computer-use.md — Let Claude use your computer from the CLI
- D4 https://code.claude.com/docs/en/desktop-scheduled-tasks.md — Schedule recurring tasks in Claude Code Desktop (matching lines only)
- D5 https://code.claude.com/docs/en/remote-control.md — Remote Control (matching lines only)
- D6 https://code.claude.com/docs/en/claude-code-on-the-web.md — Use Claude Code in the cloud (matching line only)
- D7 https://claude.com/docs/third-party/claude-desktop/browser.md — Built-in browser and Claude in Chrome
- D8 https://claude.com/docs/third-party/claude-desktop/configuration.md — Configuration reference (Capabilities and Connectors sections)
- D9 https://claude.com/docs/third-party/claude-desktop/local-access.md — Desktop and filesystem access (read, not cited)
- D10 https://claude.com/docs/cowork/changelog.md — Changelog, release notes for Claude Desktop (keyword-filtered; latest entry v2.19675.0, 2026-10-01)
- D11 https://claude.com/docs/cowork/guide/dispatch.md — Run tasks in the background with Dispatch (read, not cited)
- D12 https://claude.com/docs/cowork/overview.md — Overview (read, not cited)
- Indexes: https://code.claude.com/docs/llms.txt and https://claude.com/docs/llms.txt

Blog:

- B1 https://claude.com/blog/claude-for-chrome — Piloting Claude in Chrome (anthropic.com/news/claude-for-chrome redirects here; date not captured)

Third-party pages opened, none used as evidence:

- https://kevinwelter.com/en/blog/claude-in-chrome (2026-09-17)
- https://claude-manual.com/en/products/chrome/guide
- https://almcorp.com/blog/claude-for-chrome-complete-guide/ (2026-02-02)

## 8. What bap-browser takes from this

| Finding | Used in the spec as |
|---|---|
| Account settings are shared by web and desktop; desktop adds what needs the local machine | One catalogue; a surface shows only what it can act on (section 10.2) |
| "Preferred browser": Built-in browser or Chrome | `preferred_browser`: Cloud browser, My Chrome, Built-in browser |
| Site approval card: Allow once / Always allow / Deny, saved on the device and revocable | Site prompt in section 8.8; `approved_sites`, kept by the bridge |
| Protected actions always ask, even on an always-allowed site: downloads, sensitive information, authorisations | Consequential actions in section 8.8 |
| Permission mode chosen by the person; an admin can remove the looser modes | `ask_before` and `my_chrome_mode`; tighten-only limits and `settings.locked` |
| One organisation allow and block list covers the extension and the built-in browser | `safety.blocked_domains`, `safety.allowed_domains` and `permissions.blocked_sites` apply to every backend |
| "Clear browsing data"; "Keep cookies: Shared / Per session" | `clear_browsing_data`; `stay_signed_in` |
| Colour mode: Light / Match System / Dark | `colour_mode` |
| Notifications are opt-in, with an optional sound | `notify_when_needed` (next step) |
| Claude works in its own tab group | Section 8.8, "the agent's tab group only" |
| Automatic action screening; default blocked site categories | Later items (section 15.21) |
