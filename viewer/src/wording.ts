// Every string a person reads (spec 9.6). Sentence case; buttons start with a verb; say what will happen.

import type { ApprovalOutcome, Backend, DialogKind, EndReason, HelpKind, HelpOutcome } from './protocol';

export const W = {
  product: 'bap-browser',

  status: {
    no_agent: 'Waiting for an agent to connect',
    agent: 'Agent is working',
    waiting_for_task: 'Ready for your task',
    waiting_approval: 'Waiting for your approval',
    person_requested: 'The agent asked for help',
    person: "You're in control",
    paused: 'Paused',
    blocked: (reason: string) => `Blocked: ${reason}`,
    ended: 'Session ended',
    disconnected: 'Connection lost. Reconnecting…',
    refused: "This link can't open the session",
  },

  refused: 'Open it again from where you started the session.',

  // The words on the border of the live picture.
  label: {
    agent: 'Agent is working',
    waiting_for_task: 'Ready for your task',
    waiting_approval: 'Paused for approval',
    person_requested: 'Agent asked for help',
    person: "You're in control",
    paused: 'Paused',
    blocked: 'Blocked',
    disconnected: 'Not live',
  },

  buttons: {
    pause: 'Pause',
    resume: 'Resume',
    takeOver: 'Take over',
    handBack: 'Hand back',
    pausing: 'Pausing…',
    resuming: 'Resuming…',
    takingOver: 'Taking over…',
    handingBack: 'Handing back…',
    stop: 'Stop session',
    keepRunning: 'Keep running',
    done: 'Done',
    couldNot: "Couldn't do it",
    allowOnce: 'Allow once',
    allowSite: 'Allow on this site',
    deny: 'Deny',
    close: 'Close',
    back: 'Back',
    cancel: 'Cancel',
    clearData: 'Clear data',
    copy: 'Copy as text',
    openSettings: 'Open settings',
    showFull: 'Show the browser full width',
    showSplit: 'Show the browser beside the activity',
    viewStep: 'View step',
    dismiss: 'Dismiss',
    newSession: 'Start a new session',
  },

  ended: {
    person: 'You stopped it.',
    agent: 'The agent closed it.',
    timeout: 'It was closed after a long time with no activity.',
    failed: 'The browser stopped unexpectedly.',
  } satisfies Record<EndReason, string>,

  approval: {
    title: 'Approval needed',
    on: (site: string) => `On ${site}`,
    left: (time: string) => `${time} left, then this is denied`,
    popup: {
      title: 'The agent needs your approval',
      hint: 'The agent waits. Nothing is done until you answer.',
      hintEveryTime: 'The agent waits. This step is asked about every time: it is allowed once, or not at all.',
      later: 'Look first',
    },
    outcome: {
      allowed: 'Allowed once',
      allowed_site: 'Allowed on this site',
      denied: 'Denied',
      expired: 'No answer in time, so it was denied',
      unwatched: 'A step needed your approval and no one was watching, so it was denied.',
    } satisfies Record<ApprovalOutcome, string>,
  },

  help: {
    title: 'The agent asked for help',
    kind: {
      login: 'Sign-in needed',
      verification: 'Verification needed',
      payment: 'Payment needed',
      other: 'Your help is needed',
    } satisfies Record<HelpKind, string>,
    left: (time: string) => `${time} left, then the agent is told you could not`,
    hint: 'Take over, do the step in the browser, then choose Done.',
    popup: {
      title: {
        login: 'The agent needs you to sign in',
        verification: 'The agent needs you to pass a human check',
        payment: 'The agent needs you to make a payment',
        other: 'The agent needs your help',
      } satisfies Record<HelpKind, string>,
      hint: 'Take over, do the step in the browser, then choose Done. The agent waits and goes on from there. Nothing you type is recorded.',
      hintOwnBrowser: 'Do the step in your browser, then choose Done here. The agent waits and goes on from there.',
      doIt: "I'll do it",
      later: 'Look first',
    },
    outcome: {
      done: 'Done. The agent continues.',
      could_not: 'The agent was told you could not do it.',
      timed_out: 'No answer in time. The agent was told.',
    } satisfies Record<HelpOutcome, string>,
  },

  dialog: {
    title: 'The page opened a dialog',
    kind: {
      alert: 'Message',
      confirm: 'Question',
      prompt: 'Question with an answer',
      beforeunload: 'Leave this page?',
    } satisfies Record<DialogKind, string>,
    waiting: 'The agent is answering it.',
  },

  takeover: {
    bar: "You're in control. The agent is waiting. Nothing you type is recorded.",
    handedBack: 'Handed back. The agent will re-read the page.',
    release: (chord: string) => `Press ${chord} to leave the browser`,
  },

  stop: {
    question: 'Stop this session?',
    consequence: 'The browser will close and the agent will be told.',
  },

  frame: {
    alt: (title: string, url: string) => `Live browser view: ${title || 'untitled page'}, ${url || 'no address yet'}`,
    live: 'Live',
    connecting: 'Connecting…',
    stale: (seconds: number) => `No new picture for ${seconds} s`,
    notLive: 'Not live',
    ownBrowser: 'The agent is working in your own browser. Watch it there; its steps appear here.',
    waitingForAgent: 'Nothing to show yet',
    waitingForAgentHint: 'When an agent connects, its browser appears here.',
    noSession: 'No session to show',
    blockedPage: 'This page was blocked',
  },

  studio: {
    pages: 'Where the agent works',
    mood: {
      attention: 'Needs you',
      working: 'Working',
      ready: 'Ready',
      person: "You're in control",
      paused: 'Paused',
      stopped: 'Stopped',
    },
    off: {
      starting: 'Starting',
      waiting: 'Not connected',
      failed: 'Could not start',
    },
    starting: 'Starting the browser…',
    failed: 'The browser could not be started',
    desktop: {
      open: 'Open desktop app',
      opening: 'Opening…',
      opened: 'The desktop app is open in its own window.',
      failed: 'The desktop app could not be opened.',
    },
    connect: {
      title: 'Connect your Chrome',
      lead: 'The agent works in a tab of your own Chrome, with your sign-ins, and asks you site by site what it may do.',
      open: 'In your Chrome, open chrome://extensions and switch on Developer mode.',
      load: 'Press "Load unpacked" and choose this folder:',
      paste: 'To get there quickly, copy the folder and paste it into the file chooser: on a Mac press Cmd+Shift+G first; on Windows use its address bar.',
      icon: 'Click the BAP icon in the toolbar. It opens the chat beside your pages.',
      byItself: 'This page connects by itself, a moment after the extension is loaded.',
      copy: 'Copy the folder',
      copied: 'Copied',
    },
  },

  chat: {
    title: 'Chat',
    messages: 'Messages',
    empty: 'Tell the agent what to do in the browser. It answers here when it has finished.',
    you: 'You',
    agent: 'Agent',
    working: 'Working on it…',
    status: {
      working: 'Working',
      ready: 'Ready',
      paused: 'Paused',
      person: "You're in control",
      waiting: 'Waiting for you',
      stopped: 'Stopped',
      offline: 'Not connected',
    },
    inputLabel: 'Your task',
    placeholder: 'Give the agent a task',
    placeholderWorking: 'Add the next task',
    closed: 'The session has ended',
    startAgain: 'To work with the agent again, start a new session where you started this one.',
    send: 'Send the task',
    stopTask: 'Stop this task',
    stepsFailed: (count: number) => (count === 1 ? '1 failed' : `${count} failed`),
  },

  timeline: {
    title: 'Activity',
    empty: 'Steps appear here as the agent works.',
    idle: (seconds: number) => `idle ${seconds} s`,
    times: (count: number) => `${count} times`,
    counters: (steps: string, time: string, chars: string) => `${steps} · ${time} · ${chars}`,
    steps: (count: number) => (count === 1 ? '1 step' : `${count} steps`),
    chars: (count: string) => `${count} chars`,
    stepNumber: (n: number) => `Step ${n}`,
    failed: 'Failed',
    running: 'Running',
  },

  drawer: {
    title: (n: number) => `Step ${n}`,
    took: 'Took',
    returned: 'Returned to the agent',
    address: 'Address',
    result: 'Result',
    noPicture: 'No picture was kept for this step.',
    pictureAlt: (n: number) => `The browser at step ${n}`,
  },

  summary: {
    title: 'Session ended',
    steps: 'Steps',
    time: 'Time',
    files: 'Files saved',
    chars: 'Returned to the agent',
  },

  notice: {
    download: (name: string, size: string) => `Saved ${name} (${size})`,
    blockedTitle: 'A page was blocked',
    blockedBody: (url: string, reason: string) => `${url} was not opened: ${reason}.`,
    blockedNext: 'The agent was told and can try another way. You can also take over.',
  },

  connection: {
    connected: 'Connected',
    connecting: 'Connecting…',
    reconnecting: 'Reconnecting…',
    refused: 'Not connected',
  },

  topBar: {
    session: 'Session',
    agent: 'Agent',
    browser: 'Browser',
    sessions: 'Sessions',
    /** The page's title for a screen reader when the viewer is shown inside a client. */
    embeddedTitle: 'Browser session',
    controls: 'Session controls',
    attention: 'Needs your attention',
  },

  backend: {
    remote_headless: 'Cloud browser',
    takeover_chrome: 'My Chrome',
    bundled_chromium: 'Built-in browser',
  } satisfies Record<Backend, string>,

  settings: {
    title: 'Settings',
    groups: 'Settings groups',
    saved: 'Saved',
    savedNext: 'Saved. Applies to the next session.',
    saving: 'Saving…',
    locked: 'Set by your organisation',
    loading: 'Loading settings…',
    failed: 'The settings could not be loaded.',
    notSaved: 'Not saved: the service did not answer. Try again.',
    refused: {
      locked: "This can't be changed here: your organisation requires it.",
      would_loosen: "This can't be loosened here: your organisation requires it.",
      not_on_this_surface: "This setting isn't available here.",
      not_a_choice: "That isn't one of the choices.",
      bad_site: "That doesn't look like a site. Use a name such as example.com.",
    },
    listHint: 'One site per line. example.com also covers its subdomains.',
    listEmpty: 'No sites',
    on: 'On',
    off: 'Off',
    clear: {
      question: 'Clear cookies and site data in the cloud browser?',
      consequence: "You'll be signed out of sites there, and open sessions will end.",
      done: 'Browsing data cleared.',
      failed: 'The browsing data was not cleared: the service did not do it. Try again.',
    },
    about: {
      version: 'Version',
      browser: 'Browser in use',
      changed: 'Configuration that differs from its default',
      nothingChanged: 'Every value is at its default.',
      from: 'from',
      copied: 'Copied.',
    },
  },

  announce: {
    newStep: (text: string) => text,
    approval: (summary: string) => `Approval needed: ${summary}. Press A to go to it.`,
    help: (reason: string) => `The agent asked for help: ${reason}. Press A to go to it.`,
  },
} as const;
