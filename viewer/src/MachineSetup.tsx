import { useState } from 'react';
import { Button } from './components/StatusPanel';
import { Icon } from './components/Icon';
import { W } from './wording';

type Done = { ok: true } | { ok: false; why: string };
type Step = 'install' | 'allow';

/** The desktop on a real machine through the installed driver, while the machine still lacks
 * something: install the driver, and on macOS allow it (spec 22.10.1). */
export function MachineSetup({ note, onManage }: { note?: string; onManage?(step: Step): Promise<Done> }) {
  const [said, setSaid] = useState('');
  const [busy, setBusy] = useState<Step | null>(null);
  const take = async (step: Step) => {
    if (!onManage) return;
    setBusy(step);
    const done = await onManage(step);
    setBusy(null);
    setSaid(done.ok ? (step === 'install' ? W.studio.machine.installed : W.studio.machine.asked) : done.why);
  };
  return (
    <section className="studio-wait" aria-label={W.studio.machine.title}>
      <Icon name="computer" size="large" />
      <h2 className="studio-wait-title">{W.studio.machine.title}</h2>
      <p className="studio-wait-lead">{W.studio.machine.lead}</p>
      {note && <p className="studio-wait-note">{note}</p>}
      {onManage ? (
        <span className="studio-folder">
          <Button kind="primary" icon="play" busy={busy === 'install'} hint={W.studio.machine.installHint} onClick={() => void take('install')}>
            {W.studio.machine.install}
          </Button>
          <Button busy={busy === 'allow'} hint={W.studio.machine.allowHint} onClick={() => void take('allow')}>
            {W.studio.machine.allow}
          </Button>
        </span>
      ) : (
        <p className="studio-wait-note">{W.studio.machine.adminOnly}</p>
      )}
      {said && (
        <p className="studio-wait-note" role="status">
          {said}
        </p>
      )}
      <p className="studio-tip">{W.studio.machine.tip}</p>
    </section>
  );
}
