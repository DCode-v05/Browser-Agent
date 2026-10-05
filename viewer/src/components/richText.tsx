// What a model writes, shown the way it meant it: **bold**, `code`, [named](links) and bare
// addresses. Nothing else is interpreted, and no HTML in the text is ever used as HTML.

import type { ReactNode } from 'react';

// In order: a named link, a bare address, bold, code.
const PARTS = /\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s<>"']+)|\*\*([^*\n]+)\*\*|`([^`\n]+)`/g;
// A full stop or a bracket that ends the sentence is not part of the address before it.
const AFTER_AN_ADDRESS = /[.,;:!?)\]]+$/;

function link(address: string, text: string, key: number): ReactNode {
  return (
    <a key={key} href={address} target="_blank" rel="noopener noreferrer">
      {text}
    </a>
  );
}

export function richText(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let from = 0;
  for (const match of text.matchAll(PARTS)) {
    const [whole, name, named, bare, bold, code] = match;
    const at = match.index;
    if (at > from) out.push(text.slice(from, at));
    from = at + whole.length;
    if (named && name) out.push(link(named, name, at));
    else if (bare) {
      const address = bare.replace(AFTER_AN_ADDRESS, '');
      out.push(link(address, address, at));
      from = at + address.length;
    } else if (bold) out.push(<strong key={at}>{bold}</strong>);
    else if (code) out.push(<code key={at}>{code}</code>);
  }
  if (from < text.length) out.push(text.slice(from));
  return out;
}
