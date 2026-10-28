from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from PyQt6.QtGui import QClipboard, QGuiApplication


class NoSelection(Exception):
    pass


def get_selected_text() -> str:
    """Return the currently selected text, as HTML if available."""
    if sys.platform != "linux":
        return copy_and_paste()
    if os.environ.get("WAYLAND_DISPLAY"):
        return paste_wayland_primary()
    return paste_x11_primary()


def copy_and_paste() -> str:
    import pyautogui
    from jaraco import clipboard

    # Wait for the hotkey that triggered us to finish
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "c")
    try:
        return clipboard.paste_html()
    except Exception:
        return clipboard.paste_text()


def paste_wayland_primary() -> str:
    # Wayland only sends the selection to focused windows, so Qt can't read it from the tray;
    # wl-paste uses the data-control protocol, which doesn't need focus
    if not shutil.which("wl-paste"):
        raise NoSelection("wl-paste not found; install wl-clipboard")

    def wl_paste(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["wl-paste", "--primary", "--no-newline", *args],
            capture_output=True,
            text=True,
            timeout=2,
        )

    types = wl_paste("--list-types")
    if types.returncode != 0:
        raise NoSelection("No text selected")
    result = wl_paste("--type", "text/html" if "text/html" in types.stdout else "text")
    if result.returncode != 0 or not result.stdout:
        raise NoSelection("No text selected")
    return result.stdout


def paste_x11_primary() -> str:
    mime_data = QGuiApplication.clipboard().mimeData(QClipboard.Mode.Selection)
    if mime_data is None:
        raise NoSelection("No text selected")
    contents = mime_data.html() if mime_data.hasHtml() else mime_data.text()
    if not contents:
        raise NoSelection("No text selected")
    return contents
