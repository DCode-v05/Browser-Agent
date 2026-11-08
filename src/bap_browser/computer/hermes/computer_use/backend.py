# MIT License, Copyright (c) 2025 Nous Research. Changed only by scripts/take_hermes.py.
"""Abstract backend interface for computer use. Any implementation (cua-driver over MCP, a plugin
driver, the test noop) returns the shapes below. All methods are synchronous; async is handled inside
the backend implementation if needed. :class:`ComputerUseProvider` is the factory a provider plugin
registers (see :mod:`bap_browser.computer.seams.provider`); ``computer_use.backend`` selects exactly one."""

from __future__ import annotations

import struct
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from bap_browser.computer.seams.provider import ProviderBase

_JPEG_SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})

def image_dimensions_from_bytes(raw: bytes) -> Optional[tuple[int, int]]:
    """(width, height) for PNG / JPEG bytes, or None when unreadable. PNG: IHDR. JPEG: walk
    segments (skipping 0xFF fill bytes) to the first SOF marker; stop at SOS. Used by the
    tool layer's provider min-size guard."""
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 24:
        width, height = struct.unpack(">II", raw[16:24])
        return int(width), int(height)
    if raw.startswith(b"\xff\xd8") and len(raw) > 4:
        i = 2
        while i + 9 < len(raw):
            if raw[i] != 0xFF:
                i += 1
                continue
            marker, i = raw[i + 1], i + 2
            while marker == 0xFF and i < len(raw):
                marker, i = raw[i], i + 1
            if marker in {0xD8, 0xD9}:
                continue
            if marker == 0xDA or i + 2 > len(raw):
                break
            segment_len = int.from_bytes(raw[i:i + 2], "big")
            if segment_len < 2 or i + segment_len > len(raw):
                break
            if marker in _JPEG_SOF_MARKERS and segment_len >= 7:
                return int.from_bytes(raw[i + 5:i + 7], "big"), int.from_bytes(raw[i + 3:i + 5], "big")
            i += segment_len
    return None


@dataclass
class UIElement:
    """One interactable element on the current screen."""

    index: int
    role: str
    label: str = ""
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)
    app: str = ""
    pid: int = 0
    window_id: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)
    element_token: Optional[str] = None


@dataclass
class CaptureResult:
    """Result of a screen capture call. mode="vision" → png_b64 only; mode="ax" → elements
    only; mode="som" (default) → both: the PNG already carries numbered overlays drawn by
    the backend and `elements` holds the matching index → element mapping."""

    mode: str
    width: int
    height: int
    png_b64: Optional[str] = None
    elements: list[UIElement] = field(default_factory=list)
    app: str = ""
    window_title: str = ""
    png_bytes_len: int = 0
    image_mime_type: Optional[str] = None
    note: str = ""
    ax_max_elements: int = 0


@dataclass
class ActionResult:
    """Result of any action (click / type / scroll / drag / key / wait). ``ok`` is
    tool/transport success only — NOT the semantic verdict; read ``effect`` / ``escalation``
    (cua-driver's structured verdict) to pick the next rung of the verify → escalate ladder.
    Structured fields are optional and additive: an older driver that omits
    ``structuredContent`` leaves them ``None``, behavior unchanged.

    Beyond the transport-level ``ok`` flag, this carries cua-driver's structured action verdict so the model
    can follow the documented verify → escalate ladder (NousResearch/hermes-agent#67052).
    """

    ok: bool
    action: str
    message: str = ""
    capture: Optional[CaptureResult] = None
    meta: dict[str, Any] = field(default_factory=dict)
    verified: Optional[bool] = None
    effect: Optional[str] = None
    escalation: Optional[dict[str, Any]] = None
    path: Optional[str] = None
    degraded: Optional[bool] = None
    delivery_mode: Optional[str] = None
    code: Optional[str] = None


class ComputerUseBackend(ABC):
    """Lifecycle: `start()` before first use, `stop()` at shutdown. Pointer/keyboard actions
    take ``delivery_mode`` (background (default) | foreground) and ``bring_to_front``;
    ``button`` is left | right | middle; ``modifiers`` a list of key names. ``element`` args
    are 1-based SOM indices from a prior capture. `direction` is up | down | left | right and
    `amount` is wheel ticks; `keys` is a combo such as 'cmd+s', 'ctrl+alt+t', 'return'."""

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def capture(self, mode: str = "som", app: Optional[str] = None, pid: Optional[int] = None,
                window_id: Optional[int] = None) -> CaptureResult: ...

    @abstractmethod
    def click(self, *, element: Optional[int] = None, x: Optional[int] = None, y: Optional[int] = None,
              button: str = "left", click_count: int = 1, modifiers: Optional[list[str]] = None,
              delivery_mode: Optional[str] = None, bring_to_front: bool = False) -> ActionResult: ...

    @abstractmethod
    def drag(self, *, from_element: Optional[int] = None, to_element: Optional[int] = None,
             from_xy: Optional[tuple[int, int]] = None, to_xy: Optional[tuple[int, int]] = None,
             button: str = "left", modifiers: Optional[list[str]] = None,
             delivery_mode: Optional[str] = None, bring_to_front: bool = False) -> ActionResult: ...

    @abstractmethod
    def scroll(self, *, direction: str, amount: int = 3, element: Optional[int] = None,
               x: Optional[int] = None, y: Optional[int] = None, modifiers: Optional[list[str]] = None,
               delivery_mode: Optional[str] = None, bring_to_front: bool = False) -> ActionResult: ...

    @abstractmethod
    def type_text(self, text: str, *, delivery_mode: Optional[str] = None,
                  bring_to_front: bool = False) -> ActionResult: ...

    @abstractmethod
    def key(self, keys: str, *, delivery_mode: Optional[str] = None, bring_to_front: bool = False) -> ActionResult: ...

    @abstractmethod
    def list_apps(self) -> list[dict[str, Any]]: ...

    def list_windows(self) -> list[dict[str, Any]]:
        """Visible native windows with PID and window identifiers. Optional compatibility hook: backends that
        predate window discovery stay instantiable and report none."""
        return []

    @abstractmethod
    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult: ...

    @abstractmethod
    def set_value(self, value: str, element: Optional[int] = None) -> ActionResult: ...

    def wait(self, seconds: float) -> ActionResult:
        time.sleep(max(0.0, min(seconds, 30.0)))
        return ActionResult(ok=True, action="wait", message=f"waited {seconds:.2f}s")


class ComputerUseProvider(ProviderBase):
    """Factory for one computer_use driver, registered via ``ctx.register_computer_use_provider`` from a provider
    plugin whose directory name is the ``computer_use.backend`` value (built-in: ``plugins/computer_use/cua``). Only
    the selected provider is imported and instantiated. The model-facing tool schema is identical for every backend:
    an action the driver cannot perform returns ``ActionResult(ok=False, code="unsupported_action", message=...)``
    rather than changing the schema."""

    @abstractmethod
    def create_backend(self, *, permission_mode: str) -> ComputerUseBackend:
        """A fresh, unstarted backend for one Hermes session (the tool calls ``start()``/``stop()``).
        ``permission_mode`` is ``standard`` | ``bounded`` | ``unrestricted`` (approval bypass active)."""

    def is_available(self) -> bool:
        """Usable on this host right now (the tool's ``check_fn``). Cheap: no network, no spawning."""
        return True

    def doctor(self) -> Optional[int]:
        """``bap-browser computer doctor`` for this backend: print findings, return the exit code.
        ``None`` (default) means the backend ships no doctor."""
        return None
