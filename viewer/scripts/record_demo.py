"""Records the pictures of the viewer's demo session.

Run from the repository root:  uv run python viewer/scripts/record_demo.py

It opens the made-up site in `demo_site/`, does what the recorded agent does, and saves one
picture per step into `viewer/src/demo/frames/`, with the box of each element the agent acts on
in `viewer/src/demo/boxes.json`.
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).parent
SITE = HERE / "demo_site"
OUT = HERE.parent / "src" / "demo"
FRAMES = OUT / "frames"
WIDTH, HEIGHT = 1280, 800
JPEG_QUALITY = 72


def main() -> None:
    FRAMES.mkdir(parents=True, exist_ok=True)
    for old in FRAMES.glob("*.jpg"):
        old.unlink()
    boxes: dict[str, dict[str, int]] = {}

    def shot(page: Page, name: str) -> None:
        page.screenshot(path=str(FRAMES / f"{name}.jpg"), type="jpeg", quality=JPEG_QUALITY)

    def box(page: Page, name: str, selector: str) -> None:
        rect = page.locator(selector).bounding_box()
        assert rect is not None, selector
        boxes[name] = {
            "x": round(rect["x"]),
            "y": round(rect["y"]),
            "w": round(rect["width"]),
            "h": round(rect["height"]),
        }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})

        page.goto((SITE / "signup.html").as_uri())
        shot(page, "01-signup")
        box(page, "name", "#name")
        page.fill("#name", "Ada Lovelace")
        shot(page, "02-name")
        box(page, "email", "#email")
        page.fill("#email", "ada@example.com")
        shot(page, "03-email")
        box(page, "country", "#country")
        page.select_option("#country", "India")
        shot(page, "04-country")
        box(page, "cv", "#cv-button")
        page.set_input_files("#cv", {"name": "cv.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4"})
        shot(page, "05-file")
        box(page, "terms", "#terms")
        page.check("#terms")
        shot(page, "06-terms")
        box(page, "create", "#create")
        page.click("#create")
        page.wait_for_url("**/verify.html*")
        shot(page, "07-verify")
        box(page, "code", "#code")
        page.fill("#code", "481516")
        shot(page, "08-code")
        box(page, "continue", "#continue")
        page.click("#continue")
        page.wait_for_url("**/welcome.html*")
        shot(page, "09-welcome")
        box(page, "invoice", "#invoice")
        browser.close()

    (OUT / "boxes.json").write_text(json.dumps(boxes, indent=2) + "\n", encoding="utf-8")
    sizes = sorted((path.name, path.stat().st_size // 1024) for path in FRAMES.glob("*.jpg"))
    print("pictures (KB):", sizes)
    print("boxes:", sorted(boxes))


if __name__ == "__main__":
    main()
