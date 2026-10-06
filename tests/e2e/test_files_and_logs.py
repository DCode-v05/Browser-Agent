"""Files, the console and network logs, page scripts and dragging, in a real browser (spec 5.8, 5.9)."""

import asyncio
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bap_browser.agent.models import ref_of
from bap_browser.config import Config
from bap_browser.driver import BrowserSession, open_session
from bap_browser.tools import Toolkit

# With nobody watching, an action that needs approval is done only where the deployment says so.
UNATTENDED = {"approval_without_viewer": "allow"}


def body(text: str) -> str:
    """A result without its state block."""
    return text.split("\n[tabs]")[0]


async def finished(tools: Toolkit, count: int) -> tuple[str, str]:
    """The list of downloads once so many of them have finished, and what the agent was told
    meanwhile of what happened by itself."""
    news = ""
    async with asyncio.timeout(10):
        while True:
            listed = (await tools.call("browser_downloads", {})).text
            news += listed.partition("\n[events] ")[2]
            if listed.count(" saved at ") + listed.count(" failed: ") >= count:
                return body(listed), news
            await asyncio.sleep(0.1)


async def test_files_are_given_to_a_file_field_and_to_a_button_that_asks_for_them(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    folder = tmp_path / "uploads"
    folder.mkdir()
    (folder / "cv.txt").write_text("my cv", encoding="utf-8")
    (folder / "photo.txt").write_text("my photo", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not for any page", encoding="utf-8")
    config = make_config(tmp_path, browser={"uploads": {"allowed_dirs": [str(folder)]}}, control=UNATTENDED)
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/files.html"})
        field = ref_of(page.text, 'button "Your CV"')
        button = ref_of(page.text, 'button "Attach files"')

        one = await tools.call("browser_upload_file", {"ref": field, "paths": ["cv.txt"]})
        assert one.text.startswith(f'Uploaded cv.txt via {field} (button "Your CV").'), one.text
        assert "Chosen: cv.txt (my cv)" in (await tools.call("browser_get_text", {})).text

        # A button that opens the file chooser takes them too, by full path as well as by name.
        two = await tools.call(
            "browser_upload_file", {"ref": button, "paths": ["cv.txt", str(folder / "photo.txt")]}
        )
        assert two.text.startswith(f'Uploaded cv.txt, photo.txt via {button} (button "Attach files").')
        assert (
            "Chosen: cv.txt (my cv), photo.txt (my photo)" in (await tools.call("browser_get_text", {})).text
        )

        # Only a file in a folder uploads may come from.
        for path in (str(tmp_path / "secret.txt"), "../secret.txt"):
            outside = await tools.call("browser_upload_file", {"ref": field, "paths": [path]})
            assert outside.is_error
            assert outside.text.startswith("secret.txt is not in a folder uploads may come from ("), (
                outside.text
            )
        missing = await tools.call("browser_upload_file", {"ref": field, "paths": ["nothing.txt"]})
        assert missing.is_error and missing.text.startswith("There is no file nothing.txt in ")
        assert "not for any page" not in (await tools.call("browser_get_text", {})).text

        many = await tools.call("browser_upload_file", {"ref": field, "paths": ["cv.txt", "photo.txt"]})
        assert many.is_error and "takes one file, and 2 were given" in many.text
        wrong = await tools.call(
            "browser_upload_file", {"ref": ref_of(page.text, 'button "Not a chooser"'), "paths": ["cv.txt"]}
        )
        assert wrong.is_error and "no file chooser opened" in wrong.text


async def test_an_upload_waits_for_a_person_and_is_not_offered_where_it_could_never_be_allowed(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    folder = tmp_path / "uploads"
    folder.mkdir()
    (folder / "cv.txt").write_text("my cv", encoding="utf-8")
    uploads = {"uploads": {"allowed_dirs": [str(folder)]}}
    async with open_session(make_config(tmp_path, browser=uploads)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/files.html"})
        asked = await tools.call(
            "browser_upload_file", {"ref": ref_of(page.text, 'button "Your CV"'), "paths": ["cv.txt"]}
        )
        assert asked.is_error
        assert asked.text.startswith("This action needs a person's approval and no one is watching")
        assert "Nothing chosen" in (await tools.call("browser_get_text", {})).text

    def offered(**browser: Any) -> set[str]:
        session = BrowserSession(make_config(tmp_path, browser=browser))
        return {tool.name for tool in Toolkit(session).definitions()}

    everything = offered(javascript={"allow_evaluate": True})
    assert len(everything) == 28
    assert everything - offered() == {"browser_evaluate"}
    assert everything - offered(javascript={"allow_evaluate": True}, uploads={"enabled": False}) == {
        "browser_upload_file"
    }
    assert everything - offered(javascript={"allow_evaluate": True}, uploads={"allowed_dirs": []}) == {
        "browser_upload_file"
    }
    assert everything - offered(javascript={"allow_evaluate": True}, downloads={"enabled": False}) == {
        "browser_downloads"
    }


async def test_a_download_is_kept_in_the_downloads_folder_under_a_name_of_its_own(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    folder = tmp_path / "saved files"
    config = make_config(tmp_path, browser={"downloads": {"dir": str(folder)}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/files.html"})
        assert body((await tools.call("browser_downloads", {})).text) == (
            "No file has been downloaded in this session."
        )
        link = ref_of(page.text, 'link "Download the report"')
        clicked = await tools.call("browser_click", {"ref": link})
        first, news = await finished(tools, 1)
        assert first == f"1 download:\nreport.txt (22 bytes) saved at {folder / 'report.txt'}", first
        assert (folder / "report.txt").read_text(encoding="utf-8") == "The quarterly report.\n"
        # The agent is told when the file is there, whichever call comes next.
        assert "download saved: report.txt" in clicked.text + news

        # The same name again does not replace the first file.
        await tools.call("browser_click", {"ref": link})
        second, _ = await finished(tools, 2)
        assert second.endswith(f"report (1).txt (22 bytes) saved at {folder / 'report (1).txt'}"), second

        # A name the page suggests is never a path: the file stays inside the folder.
        await tools.call("browser_click", {"ref": ref_of(page.text, 'link "Download with a strange name"')})
        await finished(tools, 3)
        kept = sorted(file.name for file in folder.iterdir())
        assert len(kept) == 3, kept
        assert all(file.resolve().parent == folder.resolve() for file in folder.iterdir())
        assert not (tmp_path / "escape.txt").exists() and not (tmp_path.parent / "escape.txt").exists()


async def test_a_download_that_is_too_large_is_not_kept(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    folder = tmp_path / "saved files"
    config = make_config(tmp_path, browser={"downloads": {"dir": str(folder), "max_size_mb": 0}})
    async with open_session(config) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/files.html"})
        clicked = await tools.call("browser_click", {"ref": ref_of(page.text, 'link "Download the report"')})
        listed, news = await finished(tools, 1)
        assert listed == "1 download:\nreport.txt failed: it is larger than 0 MB, the most allowed", listed
        assert not folder.exists() or not list(folder.iterdir())
        assert "the download of report.txt failed: it is larger than 0 MB" in clicked.text + news


async def test_the_console(make_config: Callable[..., Config], tmp_path: Path, site: str) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/logs.html"})
        everything = body((await tools.call("browser_console", {})).text)
        lines = everything.splitlines()
        assert re.fullmatch(r"\d console messages, oldest first:", lines[0]), lines[0]
        assert lines[1:5] == [
            "[debug] starting up",
            "[info] page ready",
            "[warning] careful now",
            "[error] went wrong",
        ]
        # A picture that could not be loaded is an error the browser itself reports.
        assert any(line.startswith("[error] Failed to load resource") for line in lines[5:]), lines

        serious = body((await tools.call("browser_console", {"level": "warning"})).text)
        assert "[warning] careful now\n[error] went wrong" in serious
        assert "[info]" not in serious and "[debug]" not in serious

        # A script that breaks is in the log too. Then the log is emptied.
        await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Break"')})
        broken = body((await tools.call("browser_console", {"level": "error", "clear": True})).text)
        assert "[error] Uncaught " in broken and "null" in broken, broken
        assert body((await tools.call("browser_console", {})).text) == "The console holds no message."
        assert body((await tools.call("browser_console", {"level": "error"})).text) == (
            "The console holds no message of level error or above."
        )

        # No call returns more than the cap, however much a page writes.
        await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Chatter"')})
        capped = body((await tools.call("browser_console", {"limit": 500})).text).splitlines()
        assert capped[0] == "50 console messages, the newest of 80, oldest first:"
        assert (capped[1], capped[-1], len(capped)) == ("[info] chatter 31", "[info] chatter 80", 51)
        few = body((await tools.call("browser_console", {"limit": 2})).text).splitlines()
        assert few == [
            "2 console messages, the newest of 80, oldest first:",
            "[info] chatter 79",
            "[info] chatter 80",
        ]


async def test_the_network_log(make_config: Callable[..., Config], tmp_path: Path, site: str) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/logs.html"})
        lines = body((await tools.call("browser_network", {})).text).splitlines()
        assert re.fullmatch(r"\d requests, oldest first:", lines[0]), lines[0]
        assert f"GET 200 [document] {site}/logs.html" in lines
        assert f"GET 404 [image] {site}/missing.png" in lines

        failed = body((await tools.call("browser_network", {"failed_only": True})).text).splitlines()
        assert failed[0] == "1 request, oldest first:" and failed[1].startswith("GET 404 [image]"), failed

        await tools.call("browser_click", {"ref": ref_of(page.text, 'button "Fetch the welcome page"')})
        async with asyncio.timeout(5):
            while True:
                fetched = body((await tools.call("browser_network", {"filter": "name=Fetched"})).text)
                if fetched != "No request matches.":
                    break
                await asyncio.sleep(0.05)
        assert fetched == f"1 request, oldest first:\nGET 200 [fetch] {site}/welcome.html?name=Fetched"

        await tools.call("browser_network", {"clear": True})
        assert body((await tools.call("browser_network", {})).text) == "No request has been made."
    # The log keeps what was done, never what the page asked for.
    log = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert "missing.png" not in log


async def test_a_script_in_the_page_runs_only_where_it_is_allowed_and_approved(
    make_config: Callable[..., Config], tmp_path: Path, site: str
) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    scripts = {"javascript": {"allow_evaluate": True, "max_result_chars": 60}}
    async with open_session(make_config(tmp_path / "a", browser=scripts, control=UNATTENDED)) as session:
        tools = Toolkit(session)
        await tools.call("browser_navigate", {"url": f"{site}/logs.html"})
        value = await tools.call("browser_evaluate", {"expression": "window.answer"})
        assert body(value.text) == (
            'The script\'s value, as JSON (34 characters):\n{"total": 42, "items": ["a", "b"]}'
        ), value.text
        assert body((await tools.call("browser_evaluate", {"expression": "void 0"})).text) == (
            "The script gave no value."
        )
        broken = await tools.call("browser_evaluate", {"expression": "nope.nothing"})
        assert broken.is_error and broken.text.startswith(
            "The script failed: ReferenceError: nope is not defined"
        )
        long = await tools.call("browser_evaluate", {"expression": "'x'.repeat(500)"})
        shown = body(long.text).splitlines()
        assert shown[0] == "The script's value, as JSON (502 characters):"
        assert len(shown[1]) == 60 and shown[2] == "… 442 more characters not shown."
    log = [json.loads(line) for line in (tmp_path / "a" / "events.jsonl").read_text("utf-8").splitlines()]
    scripts_run = [line for line in log if line["tool"] == "browser_evaluate"]
    # Neither what was run nor what the page gave back is kept.
    assert scripts_run[0]["args"] == {"expression": "<13 characters>"}
    assert scripts_run[0]["result"] == "The script's value, as JSON (34 characters):"

    # Allowed, with nobody to approve it: it is not run.
    async with open_session(
        make_config(tmp_path / "b", browser={"javascript": {"allow_evaluate": True}})
    ) as session:
        tools = Toolkit(session)
        await tools.call("browser_navigate", {"url": f"{site}/logs.html"})
        unasked = await tools.call("browser_evaluate", {"expression": "document.title = 'changed'"})
        assert unasked.is_error and "needs a person's approval" in unasked.text
        assert (await tools.call("browser_snapshot", {})).text.startswith("Page: Logs\n")

    # Not allowed: there is no such tool.
    async with open_session(make_config(tmp_path / "c")) as session:
        absent = await Toolkit(session).call("browser_evaluate", {"expression": "1"})
        assert absent.is_error and absent.text.startswith("Unknown tool 'browser_evaluate'.")


async def test_dragging(make_config: Callable[..., Config], tmp_path: Path, site: str) -> None:
    async with open_session(make_config(tmp_path)) as session:
        tools = Toolkit(session)
        page = await tools.call("browser_navigate", {"url": f"{site}/drag.html"})
        knob = ref_of(page.text, 'clickable "Knob"')
        # A slider that follows the mouse: its knob is taken to a point.
        slid = await tools.call("browser_drag", {"from_ref": knob, "to_xy": [255, 270]})
        assert body(slid.text) == f'Dragged from {knob} (div "Knob") to (255, 270) (div)', slid.text
        assert "Knob at 200" in (await tools.call("browser_get_text", {})).text

        # A card that is dropped on a column, the way a page built for dragging expects it.
        card, column = ref_of(page.text, 'clickable "Card A"'), ref_of(page.text, 'clickable "Done column"')
        dropped = await tools.call("browser_drag", {"from_ref": card, "to_ref": column})
        assert body(dropped.text) == (
            f'Dragged from {card} (div "Card A") to {column} (div "Done column")'
        ), dropped.text
        assert "Dropped Card A on Done" in (await tools.call("browser_get_text", {})).text

        for arguments, problem in (
            ({"from_ref": knob}, "give either to_ref or to_xy"),
            ({"from_ref": knob, "from_xy": [1, 2], "to_xy": [3, 4]}, "give either from_ref or from_xy"),
            ({"from_xy": [1], "to_xy": [3, 4]}, "bad value for 'from_xy'"),
        ):
            bad = await tools.call("browser_drag", arguments)
            assert bad.is_error and problem in bad.text, bad.text
        outside = await tools.call("browser_drag", {"from_ref": knob, "to_xy": [9000, 10]})
        assert outside.is_error and "is outside the page" in outside.text
