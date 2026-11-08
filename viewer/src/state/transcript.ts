import type { ChatMessage, Step } from './reducer';

export type TranscriptItem =
  | { kind: 'person'; key: string; text: string }
  | { kind: 'agent'; key: string; text: string; failed: boolean }
  | { kind: 'steps'; key: string; steps: Step[] };

export function transcript(messages: readonly ChatMessage[], steps: readonly Step[]): TranscriptItem[] {
  const items: TranscriptItem[] = [];
  let m = 0;
  let s = 0;
  while (m < messages.length || s < steps.length) {
    const message = messages[m];
    const step = steps[s];
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
