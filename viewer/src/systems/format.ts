// How the Systems page writes a time, a share and an amount of money.

import { formatCount } from '../state/timeline';

const NOTHING = '–';

/** A length of time: "84 ms", "1.9 s", "2 min 5 s". A dash where there is none to say. */
export function spanOf(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return NOTHING;
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  const seconds = Math.round(ms / 1000);
  return `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}

/** A share of a whole, as a percentage. */
export function percent(share: number | null | undefined): string {
  return share === null || share === undefined ? NOTHING : `${Math.round(share * 100)}%`;
}

/** An amount in US dollars. Small amounts keep the digits that say anything. */
export function dollars(amount: number): string {
  return `$${amount >= 1 ? amount.toFixed(2) : amount.toFixed(4)}`;
}

/** The time of day a moment was, from seconds since 1970. */
export function clock(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export const count = formatCount;
