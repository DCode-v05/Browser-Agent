from importlib.resources import files

import bap_browser


def test_version_is_set() -> None:
    assert bap_browser.__version__ == "0.1.0"


def test_the_demo_site_ships_inside_the_package() -> None:
    site = files("bap_browser") / "demo_site"
    for page in ("signup.html", "verify.html", "welcome.html", "site.css"):
        assert (site / page).is_file(), page
