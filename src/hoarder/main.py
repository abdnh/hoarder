from __future__ import annotations

import html
import os
import re
import sys
import time
from pathlib import Path

import pyautogui
from jaraco import clipboard
from mss import mss
from PyQt6.QtWidgets import QApplication, QMainWindow, QSystemTrayIcon

from hoarder import cache
from hoarder.ankiconnect import AnkiConnectionFailed, add_note, gui_browse
from hoarder.config import AnkiHotkey, read_config
from hoarder.hotkeys import Hotkey, HotkeyBackend, create_backend

# from tooltip import Tooltip
from hoarder.tray import TrayIcon

SHOTS_DIR = Path("./shots").resolve()
tray_icon: TrayIcon | None = None

def take_screenshots() -> list[str]:
    with mss() as sct:
        return list(
            sct.save(output=str(SHOTS_DIR / "{date:%Y-%m-%d %H-%M-%S}-{mon}.png"))
        )


def trigger_copy() -> None:
    # Wait for the hotkey that triggered us to finish
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "c")


def truncate_text(text: str) -> str:
    if len(text) < 50:
        return text
    return text[:47] + "..."


HTML_RE = re.compile(r"<.*?>")


def strip_html(text: str) -> str:
    return html.unescape(HTML_RE.sub("", text))


current_nid: int | None = None


def on_tray_message_clicked() -> None:
    if current_nid:
        gui_browse(f"nid:{current_nid}")


def ankihotkey_callback(context: AnkiHotkey) -> None:
    trigger_copy()
    try:
        contents = clipboard.paste_html()
    except:
        contents = clipboard.paste_text()
    screenshot_paths = take_screenshots()
    screenshot_names = [os.path.basename(path) for path in screenshot_paths]
    try:
        global current_nid
        current_nid = add_note(
            context.notetype,
            context.deck,
            context.target_field,
            contents,
            context.screenshot_field,
            screenshot_paths,
        )
    except AnkiConnectionFailed:
        cache.add(context, contents, screenshot_names)
        raise Exception("Failed to connect to AnkiConnect; entry cached")
    else:
        # Commit cached entries
        for entry in cache.read():
            entry_screenshot_paths = [
                str(SHOTS_DIR / name) for name in entry.screenshot_names
            ]
            entry_hotkey_context = entry.hotkey_context
            add_note(
                entry_hotkey_context.notetype,
                entry_hotkey_context.deck,
                entry_hotkey_context.target_field,
                entry.text,
                entry_hotkey_context.screenshot_field,
                entry_screenshot_paths,
            )
        cache.write([])
    msg = f"Copied:\n{truncate_text(strip_html(contents))}"
    # tooltip.show(msg, window, period=3000)
    tray_icon.showMessage("Hoarder", msg, QSystemTrayIcon.MessageIcon.Information)


def ankihotkey_callback_wrapper(context: AnkiHotkey) -> None:
    try:
        ankihotkey_callback(context)
    except Exception as exc:
        global current_nid
        current_nid = None
        tray_icon.showMessage("Hoarder", str(exc), QSystemTrayIcon.MessageIcon.Critical)


EXIT_KEY = "Ctrl+Alt+Q"
EXIT_KEY_ID = "quit"


def register_keys(backend: HotkeyBackend) -> None:
    contexts = read_config()
    # Use the trigger as the ID so changing it in the config registers a new shortcut
    contexts_by_id = {context.hotkey: context for context in contexts}
    hotkeys = [Hotkey(EXIT_KEY_ID, EXIT_KEY, "Quit Hoarder")] + [
        Hotkey(
            context.hotkey,
            context.hotkey,
            f"Add to {context.deck} ({context.notetype})",
        )
        for context in contexts
    ]

    def on_activated(id: str) -> None:
        if id == EXIT_KEY_ID:
            QApplication.exit(0)
        elif context := contexts_by_id.get(id):
            ankihotkey_callback_wrapper(context)

    backend.activated.connect(on_activated)
    backend.failed.connect(
        lambda msg: tray_icon.showMessage(
            "Hoarder", msg, QSystemTrayIcon.MessageIcon.Critical
        )
    )
    backend.start(hotkeys)


def main() -> None:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setMinimumSize(600, 500)
    global tray_icon
    tray_icon = TrayIcon(app, window)
    tray_icon.messageClicked.connect(on_tray_message_clicked)
    tray_icon.show()


    backend = create_backend()
    register_keys(backend)

    app.exec()
    backend.stop()
