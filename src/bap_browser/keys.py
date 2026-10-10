"""Key names, in whatever dialect a model writes them, as the names the browser driver takes.

Models write `ctrl+a`, `Control+A`, `cmd+shift+t`, `Return`, `esc`, `ArrowLeft`, `pagedown`. All of
them become one form: modifiers first, joined with `+`, such as `Control+Shift+t`.
"""

from __future__ import annotations

from collections.abc import Sequence

from bap_browser.errors import BadInput

MODIFIERS = {
    "ctrl": "Control",
    "control": "Control",
    "ctl": "Control",
    "shift": "Shift",
    "alt": "Alt",
    "option": "Alt",
    "opt": "Alt",
    "cmd": "Meta",
    "command": "Meta",
    "meta": "Meta",
    "super": "Meta",
    "win": "Meta",
    "windows": "Meta",
    "controlormeta": "ControlOrMeta",
    "mod": "ControlOrMeta",
}
NAMED = {
    "enter": "Enter",
    "return": "Enter",
    "tab": "Tab",
    "space": "Space",
    "spacebar": "Space",
    "backspace": "Backspace",
    "delete": "Delete",
    "del": "Delete",
    "esc": "Escape",
    "escape": "Escape",
    "insert": "Insert",
    "ins": "Insert",
    "up": "ArrowUp",
    "arrowup": "ArrowUp",
    "down": "ArrowDown",
    "arrowdown": "ArrowDown",
    "left": "ArrowLeft",
    "arrowleft": "ArrowLeft",
    "right": "ArrowRight",
    "arrowright": "ArrowRight",
    "home": "Home",
    "end": "End",
    "pageup": "PageUp",
    "page_up": "PageUp",
    "pagedown": "PageDown",
    "page_down": "PageDown",
    "capslock": "CapsLock",
    "plus": "+",
    "minus": "-",
}
MODIFIER_ORDER = ("ControlOrMeta", "Control", "Alt", "Shift", "Meta")


def normalise(keys: str) -> str:
    """`ctrl+shift+t` becomes `Control+Shift+t`. A key that has no name here is refused."""
    held, key = _parse(keys)
    return "+".join([*held, key])


def is_typed_text(keys: str) -> bool:
    """True for what must be shown to nobody: a key press that types a character, and anything that is
    not a key press at all, which may be text an agent meant to type."""
    try:
        held, key = _parse(keys)
    except BadInput:
        return True
    return len(key) == 1 and set(held) <= {"Shift"}


def _parse(keys: str) -> tuple[list[str], str]:
    """The modifiers held, in one fixed order, and the key."""
    parts = _split(keys)
    if not parts:
        raise BadInput(
            "keys names no key. Name one such as Enter, Escape or Control+a.", reason="no key was named"
        )
    held: list[str] = []
    for part in parts[:-1]:
        modifier = MODIFIERS.get(part.lower())
        if modifier is None:
            raise BadInput(
                "Only Control, Shift, Alt and Meta can be held before a key, as in Control+a.",
                reason="the key name is not known",
            )
        if modifier not in held:
            held.append(modifier)
    held.sort(key=MODIFIER_ORDER.index)
    return held, _key(parts[-1], with_modifiers=bool(held))


def _split(keys: str) -> list[str]:
    text = keys.strip()
    if text == "+":
        return ["+"]
    # `ctrl++` is Control and the plus key.
    plus_key = text.endswith("++")
    parts = [part.strip() for part in (text[:-2] if plus_key else text).split("+")]
    if any(part == "" for part in parts):
        return []
    return [*parts, "+"] if plus_key else parts


def _key(name: str, *, with_modifiers: bool) -> str:
    low = name.lower()
    if low in NAMED:
        return NAMED[low]
    if low in MODIFIERS:
        return MODIFIERS[low]
    if len(low) >= 2 and low[0] == "f" and low[1:].isdigit() and 1 <= int(low[1:]) <= 24:
        return f"F{int(low[1:])}"
    if len(name) == 1:
        # With a modifier held, a letter is the key, not the capital: Control+a, not Control+A.
        return name.lower() if with_modifiers and name.isalpha() else name
    raise BadInput(
        "That is not a key name. Use a name such as Enter, Escape, Tab, ArrowDown, PageDown or F5, or one "
        "character. To type text, use browser_type.",
        reason="the key name is not known",
    )


def resolve_chord(keys: str, named: dict[str, int], single: dict[str, int]) -> tuple[list[str], int]:
    """The modifiers held, by the names this module gives them (`Control`, `Shift`, `Alt`, `Meta`,
    `ControlOrMeta`), and the key's own code: from `named` by its name, or from `single` by the one
    character it types. Raises `KeyError` with the key's own text for a key neither table has. A
    machine's own `chord` calls this with its own code tables, since the codes are the machine's."""
    *held, key = ["+"] if keys == "+" else keys.replace("++", "+plus").split("+")
    key = "=" if key == "plus" else key
    code = named.get(key, single.get(key.lower()) if len(key) == 1 else None)
    if code is None:
        raise KeyError(key)
    return held, code


def resolve_flags(held: Sequence[str], bits: dict[str, int], names: dict[str, str]) -> int:
    """The flags of the modifiers held, by the names this module gives them. `bits` and `names` are a
    machine's own: which bit stands for which of its own modifier names, and which of this module's
    modifier names is which of the machine's. Raises `KeyError` for a modifier `names` does not hold."""
    flags = 0
    for name in held:
        flags |= bits[names[name]]
    return flags
