import re

import pytest

from bap_browser.driver.playwright_driver import PlaywrightDriver
from bap_browser.driver.snapshot import NOTICE
from bap_browser.errors import StaleRef

HEADER = re.compile(r"Page: .*\nURL: \S+\nScroll: \d+px of \d+px \(viewport \d+px\)\n")
REF = re.compile(r"\[ref=(e\d+)\]")
ROLE_AND_NAME = re.compile(r'- (heading|textbox|combobox|radio|checkbox|button|link) "([^"]*)"')

FORM = """\
- heading "Sign up" [ref=e1] [level=1]
- textbox "Full name" [ref=e2] [required]
- textbox "Email" [ref=e3] placeholder="you@example.com" type=email
- textbox "Password" [ref=e4] type=password
- combobox "Country" [ref=e5] value="--" options=["--","India","United States"]
- radio "Free" [ref=e6] [checked]
- radio "Pro" [ref=e7] [unchecked]
- checkbox "I accept the terms" [ref=e8] [unchecked]
- button "Create account" [ref=e9]
- link "Sign in" [ref=e10]"""

STATES = """\
- button "Disabled button" [ref=e1] [disabled]
- textbox "Read only" [ref=e2] [readonly] value="fixed"
- checkbox "Tick me" [ref=e3] [unchecked]
- textbox "Notes" [ref=e4] value="first line"
- textbox "Editor" [ref=e5] value="rich"
- searchbox "Search" [ref=e6] placeholder="Find" type=search"""


async def read(
    driver: PlaywrightDriver,
    mode: str = "interactive",
    ref: str | None = None,
    max_chars: int = 20000,
    include_bboxes: bool = False,
) -> str:
    return await driver.snapshot(mode=mode, ref=ref, max_chars=max_chars, include_bboxes=include_bboxes)


def body(snapshot: str) -> str:
    """The element lines, with refs renumbered from e1 so a test does not depend on earlier tests."""
    match = HEADER.match(snapshot)
    assert match, snapshot
    numbers: dict[str, str] = {}
    return REF.sub(
        lambda m: f"[ref={numbers.setdefault(m.group(1), f'e{len(numbers) + 1}')}]", snapshot[match.end() :]
    )


async def test_the_form_reads_as_the_spec_shows(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    snapshot = await read(driver)
    assert snapshot.startswith(f"Page: Sign up\nURL: {site}/form.html\nScroll: 0px of ")
    assert body(snapshot) == FORM
    assert len(snapshot) <= 700


async def test_states_and_values(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/states.html")
    assert body(await read(driver)) == STATES


async def test_refs_are_stable_within_a_document(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    first = await read(driver)
    assert await read(driver) == first


async def test_refs_are_never_reused_after_a_navigation(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    before = {int(ref[1:]) for ref in REF.findall(await read(driver))}
    await driver.navigate(f"{site}/form.html")
    after = {int(ref[1:]) for ref in REF.findall(await read(driver))}
    assert min(after) > max(before)


async def test_roles_and_names_agree_with_playwrights_accessibility_snapshot(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/form.html")
    ours = ROLE_AND_NAME.findall(await read(driver))
    theirs = ROLE_AND_NAME.findall(await driver.page.locator("body").aria_snapshot())
    assert ours == theirs


async def test_text_that_is_not_rendered_never_appears(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/hidden.html")
    for mode in ("interactive", "all"):
        snapshot = await read(driver, mode=mode)
        assert "SECRET" not in snapshot
        assert "Hidden button" not in snapshot
        assert 'button "Visible button"' in snapshot
        assert 'button "Button in a box-less wrapper"' in snapshot
    everything = await read(driver, mode="all")
    assert '- text "Visible paragraph"' in everything
    assert '- text "Shown inside a hidden parent"' in everything


async def test_interactive_mode_leaves_text_out_and_all_mode_adds_it(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/hidden.html")
    assert "Visible paragraph" not in await read(driver)
    everything = body(await read(driver, mode="all"))
    assert everything.startswith(
        '- heading "Visible heading" [ref=e1] [level=1]\n- paragraph [ref=e2]\n  - text "Visible paragraph"'
    )


async def test_things_that_only_behave_like_buttons_are_listed_as_clickable(
    driver: PlaywrightDriver, site: str
) -> None:
    await driver.navigate(f"{site}/clickables.html")
    assert body(await read(driver)) == (
        '- clickable "Div with handler" [ref=e1]\n'
        '- clickable "Span with tab index" [ref=e2]\n'
        '- clickable "Pointer parent" [ref=e3]\n'
        '- button "Real button" [ref=e4]'
    )


async def test_a_password_is_shown_as_dots(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    await driver.page.fill("#password", "hunter2-secret")
    snapshot = await read(driver)
    assert "hunter2" not in snapshot
    assert 'textbox "Password" [ref=' in snapshot
    assert 'value="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" type=password' in snapshot


async def test_open_shadow_roots_and_slots_are_read(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/shadow.html")
    everything = await read(driver, mode="all")
    assert 'button "Shadow button"' in everything
    assert '- text "Slotted label"' in everything
    assert "Not slotted" not in everything


async def test_page_text_cannot_break_the_shape_of_the_snapshot(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/names.html")
    snapshot = await read(driver)
    assert snapshot.startswith('Page: Names "quoted" and long\n')
    lines = body(snapshot).split("\n")
    assert lines[0] == '- button "Say \\"hello\\" on two lines" [ref=e1]'
    assert lines[1] == '- button "日本語 😀 emoji" [ref=e2]'
    long_name = re.fullmatch(r'- button "((?:word )+w?o?r?d?\u2026)" \[ref=e3\]', lines[2])
    assert long_name and len(long_name.group(1)) == 120
    assert lines[3] == '- textbox "Odd type" [ref=e4]'
    assert len(lines) == 4
    assert "Odd role" not in snapshot
    assert "Forged" not in snapshot
    assert "e998" not in snapshot and "e999" not in snapshot


async def test_the_walk_stops_at_the_output_cap(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/big.html?n=5000")
    snapshot = await read(driver, max_chars=2000)
    assert len(snapshot) <= 2000
    assert snapshot.endswith(NOTICE)
    listed = REF.findall(snapshot)
    assert 20 < len(listed) < 100
    await driver.navigate(f"{site}/overlay.html")
    next_ref = int(REF.findall(await read(driver))[0][1:])
    assert next_ref - int(listed[-1][1:]) < 10, (
        "refs were handed out beyond the cap, so the walk did not stop"
    )


async def test_a_subtree_can_be_read_by_ref(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    everything = await read(driver, mode="all")
    form_ref = re.search(r"- form \[ref=(e\d+)\]", everything)
    assert form_ref
    subtree = await read(driver, ref=form_ref.group(1))
    assert 'button "Create account"' in subtree
    assert 'heading "Sign up"' not in subtree
    assert 'link "Sign in"' not in subtree


async def test_boxes_are_added_on_request(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    assert re.search(
        r'button "Create account" \[ref=e\d+\] \[box=\d+,\d+,\d+,\d+\]',
        await read(driver, include_bboxes=True),
    )
    assert "[box=" not in await read(driver)


async def test_an_unknown_or_old_ref_is_stale(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/form.html")
    old = REF.findall(await read(driver))[0]
    await driver.navigate(f"{site}/welcome.html")
    for ref in (old, "e999999"):
        with pytest.raises(StaleRef, match=f"Ref '{ref}' is stale or unknown"):
            await read(driver, ref=ref)


async def test_a_frame_is_listed_by_name(driver: PlaywrightDriver, site: str) -> None:
    await driver.navigate(f"{site}/welcome.html")
    await driver.page.evaluate(
        "() => { const f = document.createElement('iframe'); f.title = 'Payment'; f.src = 'form.html';"
        " document.body.append(f); return new Promise((done) => { f.onload = () => done(true); }); }"
    )
    snapshot = await read(driver)
    assert re.search(r'- iframe "Payment" \[ref=e\d+\]', snapshot)
    assert "Full name" not in snapshot
