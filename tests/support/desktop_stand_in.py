"""A desktop that keeps what it was asked, with no driver and no container, for tests of computer use."""

from typing import Any

from bap_browser.computer.hermes.computer_use.backend import (
    ActionResult,
    CaptureResult,
    ComputerUseBackend,
    UIElement,
)


class Desk(ComputerUseBackend):
    """A backend in the driver's place. It opens what it is asked to and shows one window of it."""

    def __init__(self) -> None:
        self.done: list[tuple[str, dict[str, Any]]] = []
        self.opened: list[str] = []

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def is_available(self) -> bool:
        return True

    def capture(
        self, mode: str = "som", app: str | None = None, pid: int | None = None, window_id: int | None = None
    ) -> CaptureResult:
        self.done.append(("capture", {"mode": mode, "app": app}))
        elements = [UIElement(index=1, role="AXButton", label="Save", bounds=(10, 10, 80, 24))]
        return CaptureResult(mode=mode, width=800, height=600, elements=elements, app="Notes")

    def click(self, **how: Any) -> ActionResult:
        self.done.append(("click", how))
        return ActionResult(ok=True, action="click")

    def drag(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="drag")

    def scroll(self, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="scroll")

    def type_text(self, text: str, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="type")

    def key(self, keys: str, **how: Any) -> ActionResult:
        return ActionResult(ok=True, action="key")

    def set_value(self, value: str, element: int | None = None) -> ActionResult:
        return ActionResult(ok=True, action="set_value")

    def list_apps(self) -> list[dict[str, Any]]:
        return [{"name": name, "pid": 7} for name in self.opened]

    def list_windows(self) -> list[dict[str, Any]]:
        return [{"title": f"Untitled 1 - {name}", "app_name": name, "pid": 7} for name in self.opened]

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        return ActionResult(ok=True, action="focus_app")

    def launch_app(self, *, bundle_id: str | None = None, name: str | None = None) -> None:
        self.opened.append(name or bundle_id or "")
