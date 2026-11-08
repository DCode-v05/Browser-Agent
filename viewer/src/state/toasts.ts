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
      return notice.outcome === 'unwatched' ? null : { key, text: W.approval.outcome[notice.outcome] };
    case 'help':
      return { key, text: W.help.outcome[notice.outcome] };
    case 'download':
      return { key, text: W.notice.download(notice.name, formatSize(notice.size)) };
  }
}
