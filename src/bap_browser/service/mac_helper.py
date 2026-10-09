"""The helper a person runs on their own Mac, so that an engine elsewhere can drive it (spec 21.13).

It answers only to the token it printed when it started, and only on the address it was given. It
opens only the apps the person named when they started it. When the person pushes the pointer into
the top left corner of the screen it stops for good: every later action is refused until it is
started again. It keeps no record of what is typed.
"""

from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable, Sequence
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from bap_browser.driver.mac_hands import MAC_APPS, Hands, chord, flags_of

STOPPED = "The person stopped the helper by moving the pointer into the corner of the screen."
BUTTONS = ("left", "right", "middle")


class Helper:
    """What the helper allows and whether it has been stopped."""

    def __init__(self, hands: Hands, token: str, apps: Sequence[str], corner: float) -> None:
        self.hands, self._token, self.apps, self._corner = hands, token, tuple(apps), corner
        self.stopped = False

    def admits(self, request: Request) -> bool:
        scheme, _, given = request.headers.get("authorization", "").partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(given.encode(), self._token.encode())

    def why_not(self) -> str | None:
        """Why no action may be done now. None when one may."""
        if self.stopped:
            return STOPPED
        x, y = self.hands.pointer_at()
        if x <= self._corner and y <= self._corner:
            self.stopped = True
            return STOPPED
        recording, accessibility = self.hands.allowed()
        if not accessibility:
            return "This Mac has not allowed the helper to use the mouse and keyboard: System Settings, Privacy & Security, Accessibility."
        if not recording:
            return "This Mac has not allowed the helper to see the screen: System Settings, Privacy & Security, Screen Recording."
        return None


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("not a number")
    return float(value)


def act(helper: Helper, asked: dict[str, Any]) -> None:
    """Does one action. Raises ValueError for one that is not well formed or not allowed."""
    hands, kind = helper.hands, asked.get("do")
    button = asked.get("button", "left")
    if button not in BUTTONS:
        raise ValueError("no such button")
    match kind:
        case "click":
            count = int(_number(asked.get("count", 1)))
            if not 1 <= count <= 3:
                raise ValueError("a click is 1 to 3 presses")
            held = asked.get("held", [])
            if not isinstance(held, list):
                raise ValueError("held is a list of modifiers")
            flags = flags_of([str(name) for name in held])
            hands.click(_number(asked["x"]), _number(asked["y"]), button, count, flags)
        case "move":
            hands.move(_number(asked["x"]), _number(asked["y"]))
        case "press":
            hands.press(_number(asked["x"]), _number(asked["y"]), button, bool(asked.get("down")))
        case "drag":
            start, end = asked["from"], asked["to"]
            hands.drag((_number(start[0]), _number(start[1])), (_number(end[0]), _number(end[1])))
        case "type":
            text = asked.get("text")
            if not isinstance(text, str):
                raise ValueError("no text")
            hands.type_text(text)
        case "key":
            down = asked.get("down")
            for _ in range(int(_number(asked.get("repeat", 1)))):
                hands.key(*chord(str(asked["keys"])), down if isinstance(down, bool) else None)
        case "scroll":
            if "x" in asked and "y" in asked:
                hands.move(_number(asked["x"]), _number(asked["y"]))
            hands.scroll(int(_number(asked.get("lines_x", 0))), int(_number(asked.get("lines_y", 0))))
        case "open":
            app = asked.get("app")
            if app not in helper.apps or app not in MAC_APPS:
                raise ValueError("the person did not allow that app on this Mac")
            hands.open_app(MAC_APPS[app])
        case _:
            raise ValueError("no such action")


def helper_app(helper: Helper) -> Starlette:
    def guarded(handle: Callable[[Request], Any]) -> Callable[[Request], Any]:
        async def checked(request: Request) -> Response:
            if not helper.admits(request):
                return Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})
            return await handle(request)

        return checked

    async def status(request: Request) -> Response:
        recording, accessibility = helper.hands.allowed()
        return JSONResponse(
            {
                "screen": list(helper.hands.screen()),
                "screen_recording": recording,
                "accessibility": accessibility,
                "stopped": helper.stopped,
                "apps": list(helper.apps),
                "front": await asyncio.to_thread(helper.hands.front),
            }
        )

    async def picture(request: Request) -> Response:
        if helper.stopped:
            return JSONResponse({"error": STOPPED}, status_code=423)
        given = request.query_params
        width = int(given.get("width", helper.hands.screen()[0]))
        quality = int(given.get("quality", 0)) or None
        part = given.get("region")
        region = tuple(int(number) for number in part.split(",")) if part else None
        if region is not None and len(region) != 4:
            return JSONResponse({"error": "a region is x, y, width and height"}, status_code=400)
        data = await asyncio.to_thread(helper.hands.picture, width, quality, region)
        return Response(data, media_type="image/jpeg" if quality else "image/png")

    async def do(request: Request) -> Response:
        why_not = helper.why_not()
        if why_not is not None:
            return JSONResponse({"error": why_not}, status_code=423)
        try:
            asked = await request.json()
            if not isinstance(asked, dict):
                raise ValueError("not an object")
            await asyncio.to_thread(act, helper, asked)
        except (ValueError, KeyError, IndexError, TypeError) as wrong:
            return JSONResponse({"error": f"The helper did not do it: {wrong}"}, status_code=400)
        return JSONResponse({"done": True})

    return Starlette(
        routes=[
            Route("/status", guarded(status), methods=["GET"]),
            Route("/picture", guarded(picture), methods=["GET"]),
            Route("/act", guarded(do), methods=["POST"]),
        ]
    )
