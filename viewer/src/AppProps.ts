// What the viewer's page is given by whoever draws it (spec 9).

import type { ReactNode } from 'react';

import type { Connection } from './connection/connection';
import type { ViewerOptions } from './options';
import type { Preferences } from './preferences';
import type { Surface } from './protocol';
import type { SettingsSource } from './settings/types';

export interface AppProps {
  /** Opens the session's connection. Called once. */
  createConnection: () => Connection;
  settings: SettingsSource;
  surface?: Surface;
  /** Shown inside a UI client, which has its own header. */
  embedded?: boolean;
  options?: ViewerOptions;
  preferences?: Preferences;
  /** The page around the app has the settings of this browser on a page of its own (spec 9.17). The
   *  settings button goes there; and that page keeps the colour mode and what the person prefers,
   *  so that they hold on its other pages too. */
  onOpenSettings?: () => void;
  /** Drawn as one page of the window of several browsers (spec 9.16). That window has the page's
   *  bar, its heading and its main part: the app is then none of them a second time. */
  inWindow?: boolean;
  beside?: boolean;
  /** Said at the top of the chat alone: which machine the engine is on and which it controls. */
  where?: ReactNode;
}
