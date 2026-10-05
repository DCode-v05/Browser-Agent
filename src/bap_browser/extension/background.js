// The extension's icon opens the chat in the side panel. That is all the background does: the agent
// drives the browser from the core, not from here.

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);
