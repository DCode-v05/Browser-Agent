"""Which files an agent may give to a page."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from bap_browser.errors import BadInput


def allowed_file(folders: Sequence[str], given: str) -> Path:
    """The file an upload names, when it is inside a folder uploads may come from
    (`browser.uploads.allowed_dirs`). A name with no folder is looked for in each of them.

    A link inside such a folder that leads out of it is followed first, and so is refused.
    """
    roots = [Path(folder).expanduser().resolve() for folder in folders]
    asked = Path(given).expanduser()
    candidates = [asked.resolve()] if asked.is_absolute() else [(root / asked).resolve() for root in roots]
    inside = [file for file in candidates if any(file.is_relative_to(root) for root in roots)]
    for file in inside:
        if file.is_file():
            return file
    places = ", ".join(str(root) for root in roots)
    if inside:
        raise BadInput(f"There is no file {asked.name} in {places}.", reason="there is no such file")
    raise BadInput(
        f"{asked.name} is not in a folder uploads may come from ({places}). "
        "Ask the person to put the file there.",
        reason="uploads from that folder are not allowed",
    )
