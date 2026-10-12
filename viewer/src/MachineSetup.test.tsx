import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MachineSetup } from './MachineSetup';
import { W } from './wording';

describe('a real machine as the desktop of computer use (spec 22.10.1)', () => {
  it('says what the machine lacks, and offers to install the driver and to allow it', async () => {
    const manage = vi.fn(async (step: string) => ({ ok: step.length > 0 }) as { ok: true });
    const user = userEvent.setup();
    render(<MachineSetup note="The driver of computer use is not installed on this machine." onManage={manage} />);
    expect(screen.getByRole('heading', { name: W.studio.machine.title })).toBeInTheDocument();
    expect(screen.getByText('The driver of computer use is not installed on this machine.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: W.studio.machine.install }));
    expect(manage).toHaveBeenLastCalledWith('install');
    expect(await screen.findByRole('status')).toHaveTextContent(W.studio.machine.installed);
    await user.click(screen.getByRole('button', { name: W.studio.machine.allow }));
    expect(manage).toHaveBeenLastCalledWith('allow');
    expect(await screen.findByRole('status')).toHaveTextContent(W.studio.machine.asked);
  });

  it('says why, when a step could not be done', async () => {
    const user = userEvent.setup();
    render(<MachineSetup onManage={async () => ({ ok: false, why: 'The driver could not be downloaded.' })} />);
    await user.click(screen.getByRole('button', { name: W.studio.machine.install }));
    expect(await screen.findByRole('status')).toHaveTextContent('The driver could not be downloaded.');
  });

  it('tells a user that the admin sets the machine up', () => {
    render(<MachineSetup />);
    expect(screen.queryByRole('button', { name: W.studio.machine.install })).not.toBeInTheDocument();
    expect(screen.getByText(W.studio.machine.adminOnly)).toBeInTheDocument();
  });
});
