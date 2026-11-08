import type { ReactNode } from 'react';

import type { Connection } from './connection/connection';
import type { ViewerOptions } from './options';
import type { Preferences } from './preferences';
import type { Surface } from './protocol';
import type { SettingsSource } from './settings/types';

export interface AppProps {
  createConnection: () => Connection;
  settings: SettingsSource;
  surface?: Surface;
  embedded?: boolean;
  options?: ViewerOptions;
  preferences?: Preferences;
  onOpenSettings?: () => void;
  inWindow?: boolean;
  beside?: boolean;
  where?: ReactNode;
}
