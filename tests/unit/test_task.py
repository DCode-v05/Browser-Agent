"""The task an agent is on, and the sites that belong to it (spec 18.3)."""

import pytest

from bap_browser.safeguards.task import TaskBook, TaskSite, sites_in


@pytest.mark.parametrize(
    ("message", "sites"),
    [
        ("Check in at skylark-air.example for flight SK4821", ["skylark-air.example"]),
        ("Open https://www.shop.example/basket?id=3 and pay", ["shop.example"]),
        ("Compare a.shop.co.uk with HTTP://Other.Example/x.", ["shop.co.uk", "other.example"]),
        ("shop.example, then shop.example again", ["shop.example"]),
        ("Find the cheapest flight to Oslo.", []),
        ("Version 2.5 costs 3.99 and file v1.2.3 is old", []),
        # The end of an email address names nobody's site.
        ("Send the report to bob@partner.example", []),
        ("Mail bob@partner.example about docs.partner.example", ["partner.example"]),
    ],
)
def test_the_sites_a_message_names_are_found(message: str, sites: list[str]) -> None:
    assert sites_in(message) == sites


def test_a_message_of_the_person_is_the_task_and_names_its_sites() -> None:
    book = TaskBook()
    assert not book.set
    book.person_said("Check in at skylark-air.example", "https://news.example/today")
    assert (book.text, book.source, book.earlier) == ("Check in at skylark-air.example", "person", [])
    assert book.sites() == [TaskSite("skylark-air.example", "named"), TaskSite("news.example", "named")]


def test_the_sites_pile_up_over_a_conversation_and_earlier_messages_are_kept() -> None:
    book = TaskBook()
    book.person_said("Open shop.example")
    book.person_said("Now compare with other.example")
    book.person_said("ok, go on")
    assert book.earlier == ["Open shop.example", "Now compare with other.example"]
    assert [site.host for site in book.sites()] == ["shop.example", "other.example"]


def test_the_open_page_is_named_only_when_its_site_has_no_grade_yet() -> None:
    book = TaskBook()
    book.person_said("Find a hotel")
    book.add("maps.example", "added_read")
    book.person_said("ok, go on", "https://maps.example/route")
    assert book.grade("maps.example") == "added_read"
    book.person_said("Book on maps.example")
    assert book.grade("maps.example") == "named", "the person named it in so many words"


def test_the_cores_own_pages_and_the_empty_page_are_no_site_of_the_task() -> None:
    book = TaskBook()
    book.own_origins.add("http://127.0.0.1:8765")
    assert book.is_own("http://127.0.0.1:8765/demo-site/checkin.html")
    assert book.is_own("about:blank") and book.is_own("")
    assert not book.is_own("http://127.0.0.1:9000/demo-site/checkin.html"), "another port is another origin"
    assert not book.is_own("https://evil.example/demo-site/")
    book.person_said("Sign me up", "http://127.0.0.1:8765/demo-site/")
    assert book.sites() == []


def test_a_task_an_agent_declares_replaces_the_one_before_and_its_sites_may_only_be_read() -> None:
    book = TaskBook()
    book.declared("Read the news", ["news.example"])
    book.add("maps.example", "added_read")
    book.declared("Buy a ticket", ["www.tickets.example", "pay.tickets.example", ""])
    assert (book.text, book.source) == ("Buy a ticket", "agent")
    assert book.sites() == [TaskSite("tickets.example", "added_read")]


def test_a_task_ends_and_only_a_conversations_sites_stay() -> None:
    chat = TaskBook()
    chat.person_said("Open shop.example")
    chat.end()
    assert not chat.set and chat.grade("shop.example") == "named"

    declared = TaskBook()
    declared.declared("Read the news", ["news.example"])
    declared.end()
    assert not declared.set and declared.sites() == []


def test_a_grade_is_only_ever_raised_and_a_named_site_stays_named() -> None:
    book = TaskBook()
    assert book.add("maps.example", "added_read")
    assert not book.add("maps.example", "added_read")
    assert book.add("maps.example", "added_act")
    assert not book.add("maps.example", "added_read")
    assert book.grade("maps.example") == "added_act"
    book.person_said("Open shop.example")
    assert not book.add("shop.example", "added_act")
    assert book.grade("shop.example") == "named"
    assert not book.add("", "added_read")


def test_a_person_can_drop_a_site_and_it_is_outside_the_task_again() -> None:
    book = TaskBook()
    book.person_said("Open shop.example")
    assert book.drop("shop.example")
    assert book.grade("shop.example") is None
    assert not book.drop("shop.example")
