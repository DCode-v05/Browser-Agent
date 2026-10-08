"""What a step does (spec 18.4): pressing this control pays, sends, deletes, gives access, or makes
something final.

It is told by words, in code, before any model is asked: a model can be talked round, and a step
that pays must reach a person whatever a model thinks of it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from functools import lru_cache
from typing import Literal

from bap_browser.config_safeguards import Actions

ActionClass = Literal["pays", "sends", "deletes", "grants", "commits"]
# The order in which a name is tried: a "Pay and send" button pays.
CLASSES: tuple[ActionClass, ...] = ("pays", "sends", "deletes", "grants", "commits")
# The classes a model is never allowed to let run by itself (the floor of 18.4).
NEVER_ON_A_MODELS_WORD = frozenset({"pays", "sends", "deletes", "grants"})
# Controls that are pressed. A field that is typed into is not classified by its name.
TYPED_INTO = frozenset({"textbox", "searchbox", "combobox", "spinbutton", "slider"})
# A link goes somewhere. Links that pay or delete exist; a link named "Blog post" sends nothing.
NOT_FOR_A_LINK = frozenset({"sends", "commits"})
# The keys that send what a message box holds.
SENDING_KEYS = frozenset({"Enter", "Control+Enter", "Meta+Enter"})


@lru_cache(maxsize=512)
def _pattern(word: str) -> re.Pattern[str] | None:
    """A word in Latin letters is matched whole, a phrase with any white space between its words.
    None for a word in another script, which is looked for anywhere: such scripts join their words."""
    if not word.isascii():
        return None
    return re.compile(r"(?<![a-z0-9])" + r"\s+".join(map(re.escape, word.lower().split())) + r"(?![a-z0-9])")


def longest_held(name: str, words: Sequence[str]) -> int:
    """How many words the longest of `words` that the name holds is made of. 0 when it holds none."""
    lowered, longest = name.lower(), 0
    for word in words:
        pattern = _pattern(word)
        if pattern.search(lowered) if pattern is not None else word.lower() in lowered:
            longest = max(longest, len(word.split()))
    return longest


def holds(name: str, words: Sequence[str]) -> bool:
    """Whether a name holds one of the words."""
    return longest_held(name, words) > 0


def class_of(
    name: str, actions: Actions, more_words: Sequence[str] = (), *, role: str = "button"
) -> ActionClass | None:
    """The class of a control that is pressed, by its name. `more_words` are the deployment's own
    consequential words (`permissions.consequential_words`): one that is in no class commits.

    A phrase says more than a word: "Cancel order" deletes, though "order" alone pays. Between
    words of the same length the graver class wins: "Confirm and pay" pays."""
    if role in TYPED_INTO:
        return None
    found: ActionClass | None = None
    most = 0
    for kind in CLASSES:
        if role == "link" and kind in NOT_FOR_A_LINK:
            continue
        held = longest_held(name, getattr(actions, kind))
        if held > most:
            found, most = kind, held
    if found is None and role != "link" and holds(name, more_words):
        return "commits"
    return found


def is_message_box(
    role: str, texts: Sequence[str], actions: Actions, *, multiline: bool, search: bool
) -> bool:
    """Whether a field is one a message is written in: a text area, an editable block, or a field
    whose name or label says so. A search box is not."""
    if search or role == "searchbox":
        return False
    return multiline or any(holds(text, actions.message_words) for text in texts)
