"""The bridge to a person's own Chrome (spec 4.9).

The extension in that Chrome dials in here and carries DevTools Protocol commands to the one tab it
is attached to. The driver reaches that tab through this relay as if the relay were a browser's own
debugging port, so the driver, the page script and every tool work as they do on any other browser.

Two connections meet here: the extension's, and the driver's. What the driver asks of "the browser"
is answered here; everything it asks of the tab is passed to the extension, and the tab's events
are passed back.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

# The name the driver knows the tab's session by. The extension knows the tab itself.
TAB_SESSION = "bap-tab"
# A driver may ask for a session with the browser as a whole, and through it for further sessions
# with the tab. There is one debugger on the tab, so each of those is another name for it.
BROWSER_SESSION = "bap-browser"
VERSION = {
    "protocolVersion": "1.3",
    "product": "Chrome/bap-browser-bridge",
    "userAgent": "bap-browser-bridge",
}
NO_EXTENSION = "The extension in Chrome is not connected."


class BridgeError(Exception):
    """The extension could not do what was asked, or is not there."""


class Bridge:
    def __init__(self, op_timeout_s: float) -> None:
        self._op_timeout_s = op_timeout_s
        self._extension: WebSocket | None = None
        self._driver: WebSocket | None = None
        self._waiting: dict[int, asyncio.Future[Any]] = {}
        self._asked = 0
        self._target: dict[str, Any] | None = None
        self._other_names: set[str] = set()
        self._connected = asyncio.Event()
        # One message at a time goes out on each connection, whoever sends it.
        self._to_extension_turn = asyncio.Lock()
        self._to_driver_turn = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._extension is not None

    async def wait_connected(self) -> None:
        """Returns once an extension has dialled in."""
        await self._connected.wait()

    # The extension's side.

    async def serve_extension(self, socket: WebSocket) -> None:
        """Carries the extension's answers and the tab's events until the extension leaves. One
        extension at a time: a second one is turned away."""
        if self._extension is not None:
            await socket.close(1013)
            return
        self._extension = socket
        self._connected.set()
        try:
            while True:
                message = json.loads(await socket.receive_text())
                if not isinstance(message, dict):
                    continue
                if isinstance(message.get("id"), int):
                    self._answered(message)
                elif message.get("method") == "forwardCDPEvent":
                    await self._pass_event(message.get("params"))
                elif message.get("method") == "detached":
                    # The person closed the tab or told Chrome to stop: the driver's browser is gone.
                    await self._drop_driver()
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            self._extension = None
            self._connected.clear()
            for waiting in self._waiting.values():
                if not waiting.done():
                    waiting.set_exception(BridgeError(NO_EXTENSION))
            self._waiting.clear()
            await self._drop_driver()

    def _answered(self, message: dict[str, Any]) -> None:
        waiting = self._waiting.pop(message["id"], None)
        if waiting is None or waiting.done():
            return
        if "error" in message:
            waiting.set_exception(BridgeError(str(message["error"])))
        else:
            waiting.set_result(message.get("result"))

    async def _ask(self, method: str, params: dict[str, Any]) -> Any:
        """Asks the extension for something and waits for its answer, but not for ever."""
        extension = self._extension
        if extension is None:
            raise BridgeError(NO_EXTENSION)
        self._asked += 1
        asked = self._asked
        waiting: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._waiting[asked] = waiting
        try:
            async with self._to_extension_turn:
                await extension.send_text(json.dumps({"id": asked, "method": method, "params": params}))
            async with asyncio.timeout(self._op_timeout_s):
                return await waiting
        except TimeoutError:
            raise BridgeError(f"The extension did not answer within {self._op_timeout_s:g} s.") from None
        finally:
            self._waiting.pop(asked, None)

    async def _pass_event(self, event: Any) -> None:
        if self._driver is None or not isinstance(event, dict):
            return
        told = {"method": event.get("method"), "params": event.get("params") or {}}
        within = event.get("sessionId")
        # An event of the tab itself is heard under every name the driver has for the tab.
        for name in [within] if within else [TAB_SESSION, *self._other_names]:
            await self._to_driver({"sessionId": name, **told})

    # The driver's side.

    async def serve_driver(self, socket: WebSocket) -> None:
        """Answers the driver as a browser's debugging port would, until the driver leaves. Leaving
        lets go of the tab: the tab itself stays as the agent left it."""
        if self._driver is not None:
            await socket.close(1013)
            return
        self._driver = socket
        # A driver asks many things at once, and the answer to one can wait on another being asked:
        # each is answered in its own time.
        answering: set[asyncio.Task[None]] = set()
        try:
            while True:
                message = json.loads(await socket.receive_text())
                if isinstance(message, dict):
                    task = asyncio.create_task(self._from_driver(message))
                    answering.add(task)
                    task.add_done_callback(answering.discard)
        except (WebSocketDisconnect, ValueError):
            pass
        finally:
            self._driver = None
            self._other_names.clear()
            for task in answering:
                task.cancel()
            await asyncio.gather(*answering, return_exceptions=True)
            if self._target is not None and self._extension is not None:
                self._target = None
                with contextlib.suppress(BridgeError):
                    await self._ask("detachFromTab", {})
            self._target = None

    async def _from_driver(self, message: dict[str, Any]) -> None:
        session = message.get("sessionId")
        reply: dict[str, Any] = {"id": message.get("id")}
        if session:
            reply["sessionId"] = session
        try:
            reply["result"] = await self._answer(
                str(message.get("method")), message.get("params") or {}, session
            )
        except BridgeError as refused:
            reply["error"] = {"code": -32000, "message": str(refused)}
        await self._to_driver(reply)

    async def _answer(self, method: str, params: dict[str, Any], session: Any) -> Any:
        if session is None or session == BROWSER_SESSION:
            # What a driver asks of the browser as a whole. There is no whole browser here, only the tab.
            if method == "Target.attachToBrowserTarget":
                return {"sessionId": BROWSER_SESSION}
            if method == "Target.attachToTarget":
                name = f"{TAB_SESSION}-{len(self._other_names) + 1}"
                self._other_names.add(name)
                return {"sessionId": name}
            if method == "Target.detachFromTarget":
                self._other_names.discard(str(params.get("sessionId")))
                return {}
            if method == "Browser.getVersion":
                return VERSION
            if method == "Browser.setDownloadBehavior":
                return {}
            if method == "Target.setAutoAttach":
                if self._target is None:
                    target: dict[str, Any] = (await self._ask("attachToTab", {}))["targetInfo"]
                    self._target = target
                    await self._to_driver(
                        {
                            "method": "Target.attachedToTarget",
                            "params": {
                                "sessionId": TAB_SESSION,
                                "targetInfo": {**target, "attached": True},
                                "waitingForDebugger": False,
                            },
                        }
                    )
                return {}
            if method == "Target.getTargetInfo":
                return {"targetInfo": self._target}
        # Everything else is for the tab, or for a frame or worker inside it, which has a session of its own.
        within = None if session in (TAB_SESSION, BROWSER_SESSION, *self._other_names) else session
        return (
            await self._ask("forwardCDPCommand", {"sessionId": within, "method": method, "params": params})
            or {}
        )

    async def _to_driver(self, message: dict[str, Any]) -> None:
        driver = self._driver
        if driver is None:
            return
        try:
            async with self._to_driver_turn:
                await driver.send_text(json.dumps(message))
        except (WebSocketDisconnect, RuntimeError):
            # The driver left while this was on its way.
            pass

    async def _drop_driver(self) -> None:
        driver, self._driver, self._target = self._driver, None, None
        self._other_names.clear()
        if driver is not None:
            with contextlib.suppress(RuntimeError):
                await driver.close()
