"""What each tool is given (spec 6): the arguments of every tool, with what is allowed of each.
A call whose arguments are not these is refused before the browser is touched.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from bap_browser.driver.base import LoadState, LogLevel
from bap_browser.tools.registry import REF_PATTERN, Args

Modifier = Literal["Alt", "Control", "Meta", "Shift"]
TAB_PATTERN = r"^t\d+$"


class NavigateArgs(Args):
    url: str


class SnapshotArgs(Args):
    mode: Literal["interactive", "all"] | None = None
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    max_chars: int | None = Field(default=None, ge=1)
    include_bboxes: bool = False


class NoArgs(Args):
    pass


class PlaceArgs(Args):
    """An element by ref, or a point of the page in pixels from its top left."""

    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    x: float | None = Field(default=None, ge=0)
    y: float | None = Field(default=None, ge=0)

    @property
    def point(self) -> tuple[float, float] | None:
        return (self.x, self.y) if self.x is not None and self.y is not None else None

    @property
    def place(self) -> str:
        """The place as a result names it: the ref, or the point."""
        return self.ref or f"({self.x:g}, {self.y:g})"


def _one_place(args: PlaceArgs, *, required: bool) -> None:
    half_a_point = (args.x is None) != (args.y is None)
    if half_a_point or (args.ref is not None and args.x is not None):
        raise ValueError("give either ref, or both x and y")
    if required and args.ref is None and args.x is None:
        raise ValueError("give ref, or both x and y")


class TargetArgs(PlaceArgs):
    @model_validator(mode="after")
    def _has_one_place(self) -> TargetArgs:
        _one_place(self, required=True)
        return self


class ClickArgs(TargetArgs):
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = Field(default=1, ge=1, le=3)
    # Pydantic copies the default for each call. A plain default, unlike a factory, appears in the schema.
    modifiers: list[Modifier] = Field(default=[])


class TextArgs(Args):
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    max_chars: int | None = Field(default=None, ge=1)


class FindArgs(Args):
    query: str = Field(min_length=1)
    limit: int | None = Field(default=None, ge=1)


class ScrollArgs(PlaceArgs):
    direction: Literal["up", "down", "left", "right"]
    amount: int = Field(default=1, ge=1, le=20)

    @model_validator(mode="after")
    def _has_at_most_one_place(self) -> ScrollArgs:
        _one_place(self, required=False)
        return self


class RefArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)


class PressKeyArgs(Args):
    keys: str
    repeat: int = Field(default=1, ge=1)
    ref: str | None = Field(default=None, pattern=REF_PATTERN)


class SelectArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    values: list[str] = Field(min_length=1)


class CheckArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    checked: bool


class FormField(Args):
    ref: str = Field(pattern=REF_PATTERN)
    value: str | bool


class FillFormArgs(Args):
    fields: list[FormField] = Field(min_length=1)


class WaitArgs(Args):
    text: str | None = Field(default=None, min_length=1)
    text_gone: str | None = Field(default=None, min_length=1)
    load_state: LoadState | None = None
    seconds: float | None = Field(default=None, ge=0)
    timeout_s: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _waits_for_one_thing(self) -> WaitArgs:
        given = [self.text, self.text_gone, self.load_state, self.seconds]
        if sum(value is not None for value in given) != 1:
            raise ValueError("give exactly one of text, text_gone, load_state, seconds")
        return self


class TypeArgs(Args):
    text: str
    ref: str | None = Field(default=None, pattern=REF_PATTERN)
    clear: bool = True
    submit: bool = False
    slowly: bool = False


class RequestHumanArgs(Args):
    reason: str = Field(min_length=1, max_length=300)
    kind: Literal["login", "verification", "payment", "other"] = "other"
    timeout_s: float | None = Field(default=None, gt=0)


class ScreenshotArgs(Args):
    full_page: bool | None = None
    annotate: bool | None = None


class ZoomArgs(Args):
    region: list[float] = Field(min_length=4, max_length=4)


class DragArgs(Args):
    from_ref: str | None = Field(default=None, pattern=REF_PATTERN)
    from_xy: list[float] | None = Field(default=None, min_length=2, max_length=2)
    to_ref: str | None = Field(default=None, pattern=REF_PATTERN)
    to_xy: list[float] | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _one_start_and_one_end(self) -> DragArgs:
        if (self.from_ref is None) == (self.from_xy is None):
            raise ValueError("give either from_ref or from_xy")
        if (self.to_ref is None) == (self.to_xy is None):
            raise ValueError("give either to_ref or to_xy")
        return self


class DialogArgs(Args):
    action: Literal["accept", "dismiss"]
    prompt_text: str | None = None


class TabsArgs(Args):
    action: Literal["list", "new", "switch", "close"]
    tab_id: str | None = Field(default=None, pattern=TAB_PATTERN)
    url: str | None = None


class ConsoleArgs(Args):
    level: LogLevel | None = None
    clear: bool = False
    limit: int | None = Field(default=None, ge=1)


class NetworkArgs(Args):
    filter: str | None = Field(default=None, min_length=1)
    failed_only: bool = False
    clear: bool = False
    limit: int | None = Field(default=None, ge=1)


class EvaluateArgs(Args):
    expression: str = Field(min_length=1)


class UploadArgs(Args):
    ref: str = Field(pattern=REF_PATTERN)
    paths: list[str] = Field(min_length=1)


class RunArgs(Args):
    code: str = Field(min_length=1)
    timeout_s: int | None = Field(default=None, ge=1)
