// The chat and the agent's steps as one conversation, in the order things happened: what the person
// asked, what the agent did about it, what it answered (spec 9.14).

import type { ChatMessage, Step } from './reducer';

export type TranscriptItem =
  | { kind: 'person'; key: string; text: string }
  | { kind: 'agent'; key: string; text: string; failed: boolean }
  /** The steps the agent took in a row, with nothing said in between. */
  | { kind: 'steps'; key: string; steps: Step[] };

export function transcript(messages: readonly ChatMessage[], steps: readonly Step[]): TranscriptItem[] {
  const items: TranscriptItem[] = [];
  let m = 0;
  let s = 0;
  while (m < messages.length || s < steps.length) {
    const message = messages[m];
    const step = steps[s];
    // At the same moment a person's task comes before the steps it led to, and an answer after them.
    const messageFirst = message !== undefined && (step === undefined || message.at < step.startedAt || (message.at === step.startedAt && message.role === 'person'));
    if (messageFirst) {
      items.push(
        message.role === 'person'
          ? { kind: 'person', key: `m${message.id}`, text: message.text }
          : { kind: 'agent', key: `m${message.id}`, text: message.text, failed: message.failed },
      );
      m += 1;
      continue;
    }
    const last = items.at(-1);
    if (last?.kind === 'steps') last.steps.push(step);
    else items.push({ kind: 'steps', key: `s${step.n}`, steps: [step] });
    s += 1;
  }
  return items;
}
