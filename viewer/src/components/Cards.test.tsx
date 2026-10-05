import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Approval } from '../state/reducer';
import { ApprovalCard } from './Cards';

const approval: Approval = { id: 'a1', tool: 'browser_click', summary: 'Clicking "Pay now" on shop.example', site: 'shop.example', everyTime: false, requestedAt: 100, expiresAt: 280 };

describe('the approval card', () => {
  it('offers once, the whole site, or no', () => {
    render(<ApprovalCard approval={approval} now={100} onAnswer={() => undefined} firstRef={null} />);
    expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual(['Allow once', 'Allow on this site', 'Deny']);
  });

  it('does not offer the whole site for an action that is asked about every time', () => {
    render(<ApprovalCard approval={{ ...approval, everyTime: true }} now={100} onAnswer={() => undefined} firstRef={null} />);
    expect(screen.getAllByRole('button').map((button) => button.textContent)).toEqual(['Allow once', 'Deny']);
  });
});
