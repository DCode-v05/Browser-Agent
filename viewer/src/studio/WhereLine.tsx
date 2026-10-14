// The line on the computer page that says where its engine runs and what it works on (spec 22.6).

import { useEffect, useState } from 'react';

import type { Surface } from '../protocol';
import type { SettingsSource } from '../settings/types';
import { W } from '../wording';
import { whereItWorks } from './where';

export function WhereLine({ runs, settings, surface }: { runs: string | undefined; settings: SettingsSource | undefined; surface: Surface }) {
  const [helperUrl, setHelperUrl] = useState('');
  useEffect(() => {
    if (runs !== 'remote' || !settings) return;
    let current = true;
    settings
      .load(surface)
      .then((answer) => {
        const found = answer.groups.flatMap((group) => group.settings).find((one) => one.id === 'computer_helper_url');
        if (current && typeof found?.value === 'string') setHelperUrl(found.value);
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [runs, settings, surface]);
  const { engine, target } = whereItWorks(runs, location.hostname, helperUrl);
  return (
    <p className="studio-where" data-testid="where-it-works">
      <span>
        {W.studio.where.engine} <b>{engine}</b>
      </span>
      <span aria-hidden="true">→</span>
      <span>
        {W.studio.where.worksOn} <b>{target}</b>
      </span>
    </p>
  );
}
