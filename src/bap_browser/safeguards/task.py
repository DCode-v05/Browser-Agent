"""The task an agent is on, and the sites that belong to it (spec 18.3).

A check can only ask "does this step serve the task?" when the engine knows the task. In the chat
it is what the person wrote. An outside agent declares it once, before it has read any page.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from bap_browser.policy.sites import origin_of, registrable_name, site_of

Grade = Literal["named", "added_read", "added_act"]
"""What the agent may do on a site without a check: `named`, read and act; `added_read`, read;
`added_act`, read and act (the check let the first acting step there run)."""
Source = Literal["person", "agent"]

# A token of two or more labels joined by dots, whose last label is letters only, with or without
# http:// in front. One that follows an `@` is the end of an email address, and names no site.
A_DOMAIN = re.compile(
    r"(?<![\w@.-])(?:https?://)?((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})(?![\w-])",
    re.IGNORECASE,
)
# Pages that are no site's: the empty page a tab starts on.
NO_SITE = ("", "about:blank")


def sites_in(message: str) -> list[str]:
    """The sites a message names, in the order it names them."""
    found: list[str] = []
    for match in A_DOMAIN.finditer(message):
        site = registrable_name(match.group(1))
        if site and site not in found:
            found.append(site)
    return found


@dataclass(frozen=True)
class TaskSite:
    host: str
    grade: Grade


class TaskBook:
    """The task of one session, the person's earlier messages, and the task's sites with their grades."""

    def __init__(self) -> None:
        self.text: str | None = None
        self.source: Source | None = None
        self.earlier: list[str] = []
        """The person's messages before the newest one, oldest first."""
        self.own_origins: set[str] = set()
        """Where the core serves its own pages: the start page and the demo site."""
        self.read_a_page = False
        """Whether the agent has been given the text of a page that is not the core's own."""
        self._sites: dict[str, Grade] = {}

    @property
    def set(self) -> bool:
        return self.text is not None

    def person_said(self, message: str, open_address: str = "") -> None:
        """A message in the chat is the task now. The sites it names are the task's, and so is the
        site of the page that was open when it was sent, unless that site has a grade already:
        "ok, go on" does not make a site the check let in for reading one the agent may act on."""
        if self.source == "person" and self.text is not None:
            self.earlier.append(self.text)
        elif self.source == "agent":
            # A task an agent declared ends when a person gives one.
            self._sites.clear()
        self.text, self.source = message, "person"
        for site in sites_in(message):
            self._sites[site] = "named"
        open_site = site_of(open_address)
        if open_site and not self.is_own(open_address):
            self._sites.setdefault(open_site, "named")

    def declared(self, task: str, sites: Sequence[str]) -> None:
        """An outside agent's task takes the place of the one before, and of its sites. A site it
        declares may be read; the first acting step there is checked."""
        self.text, self.source, self.earlier = task, "agent", []
        self._sites = {registrable_name(site): "added_read" for site in sites if registrable_name(site)}

    def end(self) -> None:
        """The task is over. In a chat the sites named so far stay, for the next message."""
        if self.source == "agent":
            self._sites.clear()
            self.source = None
        self.text = None

    def is_own(self, address: str) -> bool:
        """Whether an address is one of the core's own pages, or no site's at all."""
        return address in NO_SITE or origin_of(address) in self.own_origins

    def grade(self, site: str) -> Grade | None:
        return self._sites.get(site)

    def add(self, site: str, grade: Grade) -> bool:
        """Puts a site among the task's, or raises its grade. False when nothing changed. A named
        site stays named."""
        current = self._sites.get(site)
        if not site or current == grade or current == "named":
            return False
        if current == "added_act" and grade == "added_read":
            return False
        self._sites[site] = grade
        return True

    def drop(self, site: str) -> bool:
        """A person took a site out of the task. False when it was not one of them."""
        return self._sites.pop(site, None) is not None

    def sites(self) -> list[TaskSite]:
        return [TaskSite(host, grade) for host, grade in self._sites.items()]
