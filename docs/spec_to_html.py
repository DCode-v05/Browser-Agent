"""Makes the spec's page again from the spec: `bap-browser-spec.md` to `bap-browser-spec.html`.

Run it from the repository's folder, with nothing added to the project:

    uv run --no-project --with markdown python docs/spec_to_html.py

The page that is there gives the frame: its styles, its contents list and its script are kept, and
the contents list and the text are written again from the Markdown.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import markdown

HERE = Path(__file__).parent
CONTENTS_OPEN = '<span class="name">bap-browser spec</span>\n'
CONTENTS_CLOSE = "</nav>\n</details>\n<main>\n"
TEXT_CLOSE = "</main>"


def main(source: Path, page: Path) -> None:
    text = source.read_text(encoding="utf-8")
    frame = page.read_text(encoding="utf-8")
    head, rest = frame.split(CONTENTS_OPEN, 1)
    tail = TEXT_CLOSE + rest.split(TEXT_CLOSE, 1)[1]

    title, meta, intro, body = _parts(text)
    converter = markdown.Markdown(
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
    )
    written = converter.convert(_with_lists_apart(body))
    written = written.replace("<hr />\n", "")
    written = written.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")
    written = CHIP.sub(_chip, written)
    written = written.replace("<li>[ ] ", '<li class="ck"><span class="box" aria-hidden="true"></span>')
    written = written.replace("<li>[x] ", '<li class="ck done"><span class="box" aria-hidden="true"></span>')
    # A table whose heading row is empty has no heading row.
    written = re.sub(r"<thead>\s*<tr>\s*(?:<th></th>\s*)+</tr>\s*</thead>", "", written)
    header = (
        '<header class="doc-head">\n'
        f"<h1>{html.escape(title)}</h1>\n"
        f'<div class="meta">{"".join(f"<span>{html.escape(part)}</span>" for part in meta)}</div>\n'
        f"{markdown.markdown(intro)}\n"
        "</header>\n"
    )
    contents = _contents(converter.toc_tokens)  # type: ignore[attr-defined]
    page.write_text(
        head + CONTENTS_OPEN + contents + CONTENTS_CLOSE + header + written + "\n" + tail,
        encoding="utf-8",
        newline="\n",
    )


def _parts(text: str) -> tuple[str, list[str], str, str]:
    """The title, the line under it in its parts, the opening paragraph, and everything from the
    first section on. The contents list written in the Markdown is left out: the page has its own."""
    lines = text.split("\n")
    title = lines[0].removeprefix("# ").strip()
    first_section = next(index for index, line in enumerate(lines) if line.startswith("## "))
    opening = "\n".join(lines[1:first_section]).strip().split("\n\n")
    meta = [part.strip() for part in opening[0].split("·")]
    intro = opening[1]
    return title, meta, intro, "\n".join(lines[first_section:])


# A table cell that begins by saying when a thing is built shows that as a chip.
CHIP = re.compile(
    r"<td>(?:(Milestone (\d)|M(\d)|Next|Later|Not building)(?:[.,:]? +|(?=</td>))|(No)(?:[.,] +|(?=</td>)))"
)
CHIP_WORDS = {"Next": "next", "Later": "later", "Not building": "no", "No": "no"}


def _chip(found: re.Match[str]) -> str:
    said, number = found.group(1) or found.group(4), found.group(2) or found.group(3)
    if number:
        return f'<td><span class="ph ph-m{number}">M{number}</span>'
    shown = "Not building" if CHIP_WORDS[said] == "no" else said
    return f'<td><span class="ph ph-{CHIP_WORDS[said]}">{shown}</span>'


def _name(heading: dict[str, object]) -> str:
    return html.escape(html.unescape(str(heading["name"])), quote=True)


LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")


def _with_lists_apart(text: str) -> str:
    """A list that follows a line of text with no empty line between them is still a list."""
    out: list[str] = []
    fenced = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        previous = out[-1] if out else ""
        starts_a_list = LIST_ITEM.match(line) and previous.strip() and not LIST_ITEM.match(previous)
        if not fenced and starts_a_list and not previous.startswith((" ", "\t", "|", ">")):
            out.append("")
        out.append(line if fenced else _with_links(line))
    return "\n".join(out)


ADDRESS = re.compile(r"(?<![<(\"\w/])https?://[^\s<>|)]+")


def _with_links(line: str) -> str:
    """An address written out is a link, unless it is inside code."""
    parts = line.split("`")
    for index in range(0, len(parts), 2):
        parts[index] = ADDRESS.sub(_link, parts[index])
    return "`".join(parts)


def _link(found: re.Match[str]) -> str:
    address = found.group(0)
    kept = address.rstrip(".,;:\"'")
    return f"<{kept}>{address[len(kept):]}"


def _contents(sections: list[dict[str, object]]) -> str:
    out = ["<ul>"]
    for section in sections:
        out.append(f'<li class="s"><a href="#{section["id"]}">{_name(section)}</a>')
        children = section["children"]
        if isinstance(children, list) and children:
            out.append('<ul class="sub">')
            out += [f'<li><a href="#{child["id"]}">{_name(child)}</a></li>' for child in children]
            out.append("</ul>")
        out.append("</li>")
    out.append("</ul>")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    given = [Path(argument) for argument in sys.argv[1:3]]
    main(
        given[0] if given else HERE / "bap-browser-spec.md",
        given[1] if len(given) > 1 else HERE / "bap-browser-spec.html",
    )
