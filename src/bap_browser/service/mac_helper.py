"""The helper a person runs on their own Mac, so that an engine elsewhere can drive it (spec 21.13).

It answers only to the token it printed when it started, and only on the address it was given. It
opens only the apps the person named when they started it. When the person pushes the pointer into
the top left corner of the screen it stops for good: every later action is refused until it is
started again. It keeps no record of what is typed.
"""

from __future__ import annotations

import asyncio
import hmac
import re
from collections.abc import Callable, Sequence
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from bap_browser.driver.mac_driver import pairing_file, write_pairing
from bap_browser.driver.mac_hands import MAC_APPS, Hands, chord, flags_of

__all__ = ["Helper", "helper_app", "pairing_file", "write_pairing"]

STOPPED = "The person stopped the helper by moving the pointer into the corner of the screen."
BUTTONS = ("left", "right", "middle")
# Started with `--allow any`, the helper opens any app by its name, as the person allows.
ANY_APP = "any"
# What the person does through the viewer is marked so: their own hand is never held to the apps.
PERSON = "person"
# The agent's actions that are done in the app in front.
HELD_ACTIONS = frozenset({"click", "press", "drag", "type", "key", "scroll"})
AN_APP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._&'()+-]{0,59}")


async def watch_permissions(
    hands: Hands, on_allowed: Callable[[], None], say: Callable[[str], None], every_s: float
) -> None:
    """Has macOS ask for what is missing, says in Terminal what is allowed, and when both are,
    tells the window: `on_allowed` pairs the helper again, and the window connects by itself."""
    told: tuple[bool, bool] | None = None
    while True:
        now = await asyncio.to_thread(hands.allowed)
        if now != told:
            if told is None and not all(now):
                await asyncio.to_thread(hands.ask_for_access)
            missing = [
                name
                for name, given in zip(("Screen Recording", "Accessibility"), now, strict=True)
                if not given
            ]
            if missing:
                say(
                    f"macOS is asking: allow Terminal under {' and '.join(missing)} in System Settings, "
                    "Privacy & Security. After Screen Recording, quit Terminal and start the helper again."
                )
            else:
                say("Screen Recording and Accessibility are allowed. The window connects by itself.")
                on_allowed()
            told = now
        await asyncio.sleep(every_s)


class Helper:
    """What the helper allows and whether it has been stopped."""

    def __init__(self, hands: Hands, token: str, apps: Sequence[str], corner: float) -> None:
        self.hands, self._token, self.apps, self._corner = hands, token, tuple(apps), corner
        self.stopped = False

    @property
    def held(self) -> bool:
        """Whether the agent is held to the apps the person named: not when they allowed any app."""
        return ANY_APP not in self.apps

    @property
    def app_names(self) -> set[str]:
        return {MAC_APPS[app] for app in self.apps if app in MAC_APPS}

    def outside_the_apps(self, asked: dict[str, Any]) -> str | None:
        """Why an action of the agent may not be done in the app in front. None when it may."""
        if not self.held or asked.get("by") == PERSON or asked.get("do") not in HELD_ACTIONS:
            return None
        front = self.hands.front()
        if front in self.app_names:
            return None
        allowed = ", ".join(sorted(self.app_names)) or "none"
        return (
            f"The app in front is {front or 'none'}, which the person has not allowed on this Mac. Bring an "
            f"allowed app ({allowed}) to the front with computer_open_app, and act there."
        )

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
            app, name = asked.get("app"), asked.get("name")
            if isinstance(app, str) and app in helper.apps and app in MAC_APPS:
                hands.open_app(MAC_APPS[app])
            elif isinstance(name, str) and ANY_APP in helper.apps:
                if not AN_APP_NAME.fullmatch(name):
                    raise ValueError("that is not the name of an app")
                hands.open_app(name)
            else:
                raise ValueError("the person did not allow that app on this Mac")
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
            outside = helper.outside_the_apps(asked)
            if outside is not None:
                return JSONResponse({"error": outside}, status_code=423)
            # An app that the agent's action starts and that the person did not allow is closed at once,
            # as when an icon in the Dock is clicked.
            watching = helper.held and asked.get("by") != PERSON
            before = await asyncio.to_thread(helper.hands.running) if watching else {}
            await asyncio.to_thread(act, helper, asked)
            closed: list[str] = []
            if watching:
                after = await asyncio.to_thread(helper.hands.running)
                for name, pid in after.items():
                    if name not in before and name not in helper.app_names:
                        await asyncio.to_thread(helper.hands.quit_app, pid)
                        closed.append(name)
        except (ValueError, KeyError, IndexError, TypeError) as wrong:
            return JSONResponse({"error": f"The helper did not do it: {wrong}"}, status_code=400)
        if closed:
            return JSONResponse(
                {
                    "error": f"That started {', '.join(closed)}, which the person has not allowed on this Mac: "
                    "it was closed. Do not try to open it another way."
                },
                status_code=423,
            )
        return JSONResponse({"done": True})

    return Starlette(
        routes=[
            Route("/status", guarded(status), methods=["GET"]),
            Route("/picture", guarded(picture), methods=["GET"]),
            Route("/act", guarded(do), methods=["POST"]),
        ]
    )
