from __future__ import annotations

import itertools
import os
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from mss import mss

from hoarder.portal import PortalConnection, PortalError

_portal: PortalConnection | None = None


def take_screenshots(shots_dir: Path) -> list[str]:
    """Save a screenshot of each monitor to `shots_dir` and return their paths."""
    if sys.platform == "linux" and os.environ.get("WAYLAND_DISPLAY"):
        return [take_portal_screenshot(shots_dir)]
    with mss() as sct:
        return list(
            sct.save(output=str(shots_dir / "{date:%Y-%m-%d %H-%M-%S}-{mon}.png"))
        )


def take_portal_screenshot(shots_dir: Path) -> str:
    """Take a screenshot of all monitors through the XDG desktop portal (Wayland can't be captured directly)."""
    global _portal
    if _portal is None:
        _portal = PortalConnection()
    token = _portal.new_token()
    results = _portal.request(
        "org.freedesktop.portal.Screenshot",
        "Screenshot",
        "sa{sv}",
        ("", {"handle_token": ("s", token), "interactive": ("b", False)}),
        token,
        # The first screenshot may wait for the user to grant permission
        timeout=60,
    )
    uri = urlparse(results["uri"][1])
    if uri.scheme != "file":
        raise PortalError(f"Unexpected screenshot URI: {uri.geturl()}")
    source = Path(unquote(uri.path))
    # Monitor 0 means all monitors, as in mss
    stem = f"{time.strftime('%Y-%m-%d %H-%M-%S')}-0"
    dest = shots_dir / f"{stem}{source.suffix}"
    # Avoid overwriting a shot from the same second, which Anki may already reference
    for i in itertools.count(1):
        if not dest.exists():
            break
        dest = shots_dir / f"{stem}-{i}{source.suffix}"
    shutil.move(source, dest)
    return str(dest)
