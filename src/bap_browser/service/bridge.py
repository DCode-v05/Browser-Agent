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
import hmac
import json
import secrets
import time
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

from bap_browser.config import Config

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
NO_EXTENSION = "The browser on the person's machine is not connected."
# What the agent is told when the extension did not let a call through (spec 8.8).
NOT_ALLOWED = "The person has not allowed actions on {site}."
NO_ANSWER = "The person did not answer, so this action was cancelled."


# What `_answer` gives for a command it does not answer itself: the command is the tab's.
FOR_THE_TAB: Any = object()


def _refusal(driver_id: Any, session: Any, message: str) -> dict[str, Any]:
    reply: dict[str, Any] = {"id": driver_id, "error": {"code": -32000, "message": message}}
    if session:
        reply["sessionId"] = session
    return reply


class BridgeError(Exception):
    """The extension could not do what was asked, or is not there."""


class Bridge:
    def __init__(self, config: Config, own_address: str = "") -> None:
        """`own_address` is where this service is reached. The extension lets the agent open pages
        from there (its start page) without asking."""
        self._settings = config.bridge
        self._permissions = config.permissions
        self.own_address = own_address
        self._op_timeout_s = config.bridge.op_timeout_ms / 1000
        # A pairing token lets an extension in once. The key it is given then lets it come back.
        self._pairing: tuple[str, float] | None = None
        self._key: str | None = None
        self._giving_up: asyncio.Task[None] | None = None
        self._extension: WebSocket | None = None
        self._driver: WebSocket | None = None
        self._waiting: dict[int, asyncio.Future[Any]] = {}
        # The driver's commands that are with the extension now: whose they are, and the timer
        # that answers for the extension when it does not.
        self._forwarded: dict[int, tuple[Any, Any, asyncio.TimerHandle]] = {}
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

    # Pairing (spec 4.9).

    def pairing_token(self) -> str:
        """A new token that lets one extension in, once, for `bridge.pairing_ttl_s`. The one before
        it is no longer taken."""
        token = secrets.token_urlsafe(32)
        self._pairing = (token, time.monotonic() + self._settings.pairing_ttl_s)
        return token

    def admit(self, first: dict[str, Any]) -> dict[str, Any] | None:
        """What an extension that may come in is told, or None for one that may not. A pairing token
        is taken once; the key given for it lets the same extension come back after a cut."""
        given, key = first.get("token"), first.get("key")
        if isinstance(key, str) and self._key is not None and hmac.compare_digest(key, self._key):
            pass
        elif (
            isinstance(given, str)
            and self._pairing is not None
            and time.monotonic() < self._pairing[1]
            and hmac.compare_digest(given, self._pairing[0])
        ):
            self._pairing = None
            self._key = secrets.token_urlsafe(32)
        else:
            return None
        permissions = self._permissions
        return {
            "type": "paired",
            "key": self._key,
            "heartbeat_s": self._settings.heartbeat_s,
            "dead_after_s": self._settings.dead_after_s,
            "op_timeout_ms": self._settings.op_timeout_ms,
            "own_address": self.own_address,
            "mode": permissions.mode,
            "default_site_permission": permissions.default_site_permission,
            "blocked_sites": list(permissions.blocked_sites),
            "preview_timeout_s": permissions.preview_timeout_s,
        }

    # The extension's side.

    async def serve_extension(self, socket: WebSocket, *, attached: bool = False) -> None:
        """Carries the extension's answers and the tab's events until the extension leaves or falls
        silent. An extension that comes back takes the place of the connection it had; `attached`
        says whether it still holds the agent's tab."""
        if self._extension is not None:
            # The connection it had is dead, whether or not that has been noticed here yet.
            with contextlib.suppress(RuntimeError):
                await self._extension.close()
        if self._giving_up is not None:
            self._giving_up.cancel()
            self._giving_up = None
        if self._target is not None and not attached:
            # It came back without the tab: the person closed it meanwhile.
            await self._drop_driver()
        self._extension = socket
        self._connected.set()
        try:
            while True:
                # A bridge that is alive says so. One that has fallen silent is let go.
                async with asyncio.timeout(self._settings.dead_after_s):
                    message = json.loads(await socket.receive_text())
                if not isinstance(message, dict):
                    continue
                if isinstance(message.get("id"), int):
                    if message["id"] in self._forwarded:
                        # The answer to a command of the driver's goes to the driver from here, in
                        # its turn. A driver must hear what a tab said in the order the tab said it:
                        # an event that overtook the answer before it would be about a frame the
                        # driver has not heard of yet, and be dropped.
                        await self._answer_driver(message)
                    else:
                        self._answered(message)
                elif message.get("type") == "ping":
                    async with self._to_extension_turn:
                        await socket.send_text('{"type":"pong"}')
                elif message.get("method") == "forwardCDPEvent":
                    await self._pass_event(message.get("params"))
                elif message.get("method") == "detached":
                    # The person closed the tab or told Chrome to stop: the driver's browser is gone.
                    await self._drop_driver()
        except TimeoutError:
            with contextlib.suppress(RuntimeError):
                await socket.close()
        except (WebSocketDisconnect, ValueError, RuntimeError):
            pass
        finally:
            if self._extension is socket:
                self._extension = None
                self._connected.clear()
                for waiting in self._waiting.values():
                    if not waiting.done():
                        waiting.set_exception(BridgeError(NO_EXTENSION))
                self._waiting.clear()
                for asked in list(self._forwarded):
                    await self._answer_driver({"id": asked, "error": NO_EXTENSION})
                # The channel may only be cut: the extension dials again by itself. The driver keeps
                # its tab for a while, and is let go when nobody came back.
                self._giving_up = asyncio.create_task(self._give_up_later())

    async def permit_done(self) -> None:
        """The call the extension was asked about has finished: what was allowed once is over."""
        if self._extension is not None:
            with contextlib.suppress(BridgeError):
                await self._ask("permitDone", {})

    async def _give_up_later(self) -> None:
        await asyncio.sleep(self._settings.reconnect_grace_s)
        self._giving_up = None
        if self._extension is None:
            await self._drop_driver()

    async def close(self) -> None:
        """The service is stopping: nothing waits for an extension any more."""
        if self._giving_up is not None:
            self._giving_up.cancel()
            self._giving_up = None
        await self._drop_driver()

    async def permit(self, kind: str, url: str, summary: str) -> str | None:
        """Asks the extension whether the agent may read or act on a site (spec 8.8). The extension
        decides from what the person chose, and asks them when they have not. None when the call may
        go on; otherwise what the agent is told."""
        wait_s = self._permissions.preview_timeout_s + self._settings.answer_margin_s
        try:
            answer = await self._ask("permit", {"kind": kind, "url": url, "summary": summary}, wait_s)
        except BridgeError as failed:
            return str(failed)
        if not isinstance(answer, dict) or answer.get("allowed") is True:
            return None
        if answer.get("reason") == "timeout":
            return NO_ANSWER
        return NOT_ALLOWED.format(site=answer.get("site") or "this site")

    def _answered(self, message: dict[str, Any]) -> None:
        waiting = self._waiting.pop(message["id"], None)
        if waiting is None or waiting.done():
            return
        if "error" in message:
            waiting.set_exception(BridgeError(str(message["error"])))
        else:
            waiting.set_result(message.get("result"))

    async def _ask(self, method: str, params: dict[str, Any], wait_s: float | None = None) -> Any:
        """Asks the extension for something and waits for its answer, but not for ever. While the
        channel is cut, the question waits `bridge.reconnect_grace_s` for the extension to come back."""
        wait_s = self._op_timeout_s if wait_s is None else wait_s
        if self._extension is None and self._key is not None:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(self._settings.reconnect_grace_s):
                    await self._connected.wait()
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
            async with asyncio.timeout(wait_s):
                return await waiting
        except TimeoutError:
            raise BridgeError(f"The extension did not answer within {wait_s:g} s.") from None
        except (WebSocketDisconnect, RuntimeError):
            raise BridgeError(NO_EXTENSION) from None
        finally:
            self._waiting.pop(asked, None)

    async def _forward(self, driver_id: Any, session: Any, within: Any, method: str, params: Any) -> None:
        """Hands a command of the driver's to the extension. Its answer is passed back when it comes
        (`_answer_driver`), in order with the tab's events."""
        if self._extension is None and self._key is not None:
            with contextlib.suppress(TimeoutError):
                async with asyncio.timeout(self._settings.reconnect_grace_s):
                    await self._connected.wait()
        extension = self._extension
        if extension is None:
            await self._to_driver(_refusal(driver_id, session, NO_EXTENSION))
            return
        self._asked += 1
        asked = self._asked
        loop = asyncio.get_running_loop()
        late = f"The extension did not answer within {self._op_timeout_s:g} s."
        timer = loop.call_later(
            self._op_timeout_s,
            lambda: loop.create_task(self._answer_driver({"id": asked, "error": late})),
        )
        self._forwarded[asked] = (driver_id, session, timer)
        forwarded = {"sessionId": within, "method": method, "params": params}
        try:
            async with self._to_extension_turn:
                await extension.send_text(
                    json.dumps({"id": asked, "method": "forwardCDPCommand", "params": forwarded})
                )
        except (WebSocketDisconnect, RuntimeError):
            await self._answer_driver({"id": asked, "error": NO_EXTENSION})

    async def _answer_driver(self, message: dict[str, Any]) -> None:
        held = self._forwarded.pop(message["id"], None)
        if held is None:
            return
        driver_id, session, timer = held
        timer.cancel()
        if "error" in message:
            await self._to_driver(_refusal(driver_id, session, str(message["error"])))
            return
        reply: dict[str, Any] = {"id": driver_id, "result": message.get("result") or {}}
        if session:
            reply["sessionId"] = session
        await self._to_driver(reply)

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
        method, params = str(message.get("method")), message.get("params") or {}
        try:
            result = await self._answer(method, params, session)
        except BridgeError as refused:
            await self._to_driver(_refusal(message.get("id"), session, str(refused)))
            return
        if result is FOR_THE_TAB:
            # A frame or a worker inside the tab has a session of its own, which the extension knows.
            within = None if session in (TAB_SESSION, BROWSER_SESSION, *self._other_names) else session
            await self._forward(message.get("id"), session, within, method, params)
            return
        reply: dict[str, Any] = {"id": message.get("id"), "result": result}
        if session:
            reply["sessionId"] = session
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
        # Everything else is for the tab, or for a frame or worker inside it.
        return FOR_THE_TAB

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
