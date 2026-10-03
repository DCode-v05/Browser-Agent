"""What an installed bap-browser contains. Build the viewer first: npm --prefix viewer run build"""

import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_the_wheel_carries_the_viewer_the_demo_site_and_the_page_script(tmp_path: Path) -> None:
    built = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert built.returncode == 0, built.stderr
    (wheel,) = tmp_path.glob("bap_browser-*.whl")
    names = set(zipfile.ZipFile(wheel).namelist())
    assert "bap_browser/driver/snapshot_page.js" in names
    assert "bap_browser/demo_site/signup.html" in names
    assert "bap_browser/viewer_dist/index.html" in names
    assert any(name.startswith("bap_browser/viewer_dist/assets/") and name.endswith(".js") for name in names)
