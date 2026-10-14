// What a notice of the session says for a moment at the edge of the page (spec 9).

import { W } from '../wording';
import type { Notice } from './reducer';
import { formatSize } from './timeline';

export interface Toast {
  key: string;
  text: string;
}

export function toastFor(notice: Notice): Toast | null {
  const key = `notice-${notice.id}`;
  switch (notice.kind) {
    case 'approval':
      // Nobody saw that approval, so it stays on screen as a card until someone does.
      return notice.outcome === 'unwatched' ? null : { key, text: W.approval.outcome[notice.outcome] };
    case 'help':
      return { key, text: W.help.outcome[notice.outcome] };
    case 'download':
      return { key, text: W.notice.download(notice.name, formatSize(notice.size)) };
  }
}
