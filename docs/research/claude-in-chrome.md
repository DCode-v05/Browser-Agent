# How Claude's Chrome extension is built, as a reference for take-over Chrome

Researched on the web on 2026-10-05. Each point says where it comes from: **A** is Anthropic's own
pages, **T** is a third party who took the extension apart (version 1.0.56, March 2026; the store now
lists 1.0.98), **C** is Chrome's own documentation. The pages were read through a summarising tool,
so check any quoted wording on the live page before copying it.

## How it is built

- Manifest V3, a React side panel, a service worker. Permissions include sidePanel, debugger, tabGroups, tabs, scripting, nativeMessaging, offscreen, notifications. (T, A)
- It drives a page through `chrome.debugger` (the DevTools Protocol): attach, `Input.dispatchMouseEvent`, `Input.insertText`, `Page.captureScreenshot`, detach when the loop ends. (T)
- It reads a page as a screenshot plus an accessibility tree from an injected script, with a ref for each element, capped at 50,000 characters. (T)
- One tab group per session; it acts only on tabs in that group, and the person drags tabs in. (A)
- The agent loop ran inside the extension in 1.0.56 (T). Since August 2026 the panel runs a session whose loop is on Anthropic's servers (A), so the extension is probably now the executor of tool calls.
- Claude Code reaches it through a native messaging host, and a cloud bridge over WebSocket has been observed. (A, T)

## What the person sees

- The toolbar icon opens the chat in the side panel. (A)
- The agent's tabs sit in their own coloured tab group, which shows loading dots and then a check mark. (A, T)
- In the page: a pulsing glow around the edge and an injected stop button. (T)
- Chrome's own bar on every tab: "started debugging this browser". (T)
- It shows a plan first (sites and approach) with "Approve plan" or "Make changes". (A)
- It keeps working when the person switches tabs, and notifies with a sound when it needs them or has finished. (A)
- On a sign-in page or a CAPTCHA it stops and asks the person to do it. (A)

## Human in the loop

- Three modes: approve by hand, approve automatically (the default), skip all approvals. (A)
- The site prompt offers: allow all for this website, allow this time only, deny. (A)
- It always asks, even on an allowed site, before a download, entering sensitive information, or granting an authorisation. It says it never buys, creates accounts, enters card data, deletes permanently, or follows instructions found in a page. (A)
- Before each action that changes something it checks that the tab is still on the same site. (T)

## How others connect an agent to a local Chrome

- **Playwright MCP, extension mode:** the server starts a local relay; the extension is given the relay's address and dials out; messages are `chrome.debugger` attach, sendCommand, onEvent and onDetach relayed as they are. The closest design to our bridge. (source: the Playwright repository)
- Nanobrowser: no transport, the agent runs in the service worker. chrome-devtools-mcp and browser-use: no extension, they attach by the debugging port, which Chrome 136 and later refuses on the default profile.

## Limits of the platform to design around (C)

- `chrome.debugger` cannot attach to `chrome://` pages or the Web Store, and a new tab must have loaded before attach.
- The debugging bar cannot be hidden without a launch flag or a policy install.
- A service worker stops after 30 s idle. Traffic on a WebSocket keeps it alive from Chrome 116: send something every 20 s.
- `sidePanel.open()` needs a click from the person; the panel's width cannot be set.
- Outside the Web Store, an extension is installed unpacked in developer mode. `--load-extension` no longer works in branded Chrome from version 137.

## Not found

How the side panel draws each step and its result; whether there is an agent pointer; pause as
distinct from stop. These need a look at the live product.

## Sources

- https://support.claude.com/en/articles/12012173-getting-started-with-claude-in-chrome
- https://support.claude.com/en/articles/12902446-claude-in-chrome-permissions-guide
- https://support.claude.com/en/articles/12902428-using-claude-in-chrome-safely
- https://code.claude.com/docs/en/chrome
- https://claude.com/blog/claude-in-chrome-generally-available
- https://gist.github.com/sshh12/e352c053627ccbe1636781f73d6d715b
- https://cheq.ai/blog/the-cyborg-session-reversing-detecting-claude-ai-agent-chrome-extension/
- https://github.com/microsoft/playwright/tree/main/packages/extension
- https://developer.chrome.com/docs/extensions/reference/api/debugger
- https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- https://developer.chrome.com/docs/extensions/reference/api/sidePanel
- https://developer.chrome.com/docs/extensions/how-to/distribute/install-extensions
