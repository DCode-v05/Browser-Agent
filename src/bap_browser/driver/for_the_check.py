"""What the check on a step asks of a page (spec 18.4): what a press would land on, what the page
is about, where the browser is, what the last read left out, and whether a step changed anything.
"""

from __future__ import annotations

from typing import Any

from bap_browser.driver.acting import Acting
from bap_browser.driver.base import Located


class ForTheCheck(Acting):
    async def locate_point(self, x: float, y: float) -> Located | None:
        return await self._locate_without_a_ref({"x": x, "y": y})

    async def locate_focus(self) -> Located | None:
        return await self._locate_without_a_ref({"focused": True})

    async def _locate_without_a_ref(self, how: dict[str, Any]) -> Located | None:
        tab = self._active
        if tab is None:
            return None
        found = await tab.script.call("locate", {**how, **self._what_to_locate(press=True)})
        return None if found.get("error") else self._located(found)

    async def gist(self) -> list[str]:
        tab = self._active
        if tab is None:
            return []
        said = await tab.script.call(
            "gist",
            {
                "limit": self._config.safeguards.outgoing.consent_texts,
                "maxName": self._config.browser.snapshot.max_name_chars,
            },
        )
        return [str(text) for text in said]

    def where(self) -> tuple[str, str]:
        tab = self._active
        return ("", "") if tab is None else (tab.id, tab.page.url)

    def unseen(self) -> list[str]:
        tab = self._active
        return [] if tab is None else list(tab.unseen)

    async def change_mark(self) -> str | None:
        tab = self._active
        if tab is None:
            return None
        wait_ms = self._config.browser.timeouts.change_wait_ms
        in_the_page = await tab.script.stamp(wait_ms)
        if in_the_page is None:
            return None
        # A frame that has gone away says nothing, and its going was a change of the page around it.
        in_frames = [await frame.script.stamp(wait_ms) for frame in list(tab.frames.values())]
        return f"{tab.id} {tab.commits} {tab.page.url} {in_the_page} {in_frames}"
