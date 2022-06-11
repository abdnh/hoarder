import html
import os
from pathlib import Path
import re
import sys
import time
from typing import List

from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import QAbstractNativeEventFilter, QAbstractEventDispatcher
from pyqtkeybind import keybinder
from mss import mss
import pyautogui
from jaraco import clipboard

from ankiconnect import add_note, store_media
from config import AnkiHotkey, read_config

# from tooltip import Tooltip
from tray import TrayIcon

sct = mss()

SHOTS_DIR = Path("./shots")


def take_screenshot() -> str:
    path = str(SHOTS_DIR / "{date:%Y-%m-%d %H-%M-%S}.png")
    return sct.shot(output=path)


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


def ankihotkey_callback(context: AnkiHotkey):
    trigger_copy()
    screenshot_filename = take_screenshot()
    screenshot_path = os.path.abspath(screenshot_filename)
    store_media(screenshot_path)
    contents = clipboard.paste_html()
    nid = add_note(
        context.notetype,
        context.deck,
        context.target_field,
        contents,
        context.screenshot_field,
        screenshot_path,
    )
    msg = f"Copied:\n{truncate_text(strip_html(contents))}"
    # tooltip.show(msg, window, period=3000)
    tray_icon.showMessage("Hoarder", msg, QSystemTrayIcon.MessageIcon.Information)


def ankihotkey_callback_wrapper(context: AnkiHotkey) -> None:
    try:
        ankihotkey_callback(context)
    except Exception as exc:
        tray_icon.showMessage("Hoarder", str(exc), QSystemTrayIcon.MessageIcon.Critical)


def register_keys() -> List[AnkiHotkey]:
    anki_hotkeys = read_config()
    win_id = window.winId()
    for context in anki_hotkeys:
        keybinder.register_hotkey(
            win_id,
            context.hotkey,
            lambda context=context: ankihotkey_callback_wrapper(context),
        )
    return anki_hotkeys


def unregister_keys(anki_hotkeys: List[AnkiHotkey]) -> None:
    win_id = window.winId()
    for context in anki_hotkeys:
        keybinder.unregister_hotkey(win_id, context.hotkey)


class WinEventFilter(QAbstractNativeEventFilter):
    def __init__(self, keybinder):
        self.keybinder = keybinder
        super().__init__()

    def nativeEventFilter(self, eventType, message):
        ret = self.keybinder.handler(eventType, message)
        return ret, 0


app = QApplication(sys.argv)
window = QMainWindow()
window.setMinimumSize(600, 500)

tray_icon = TrayIcon(app, window)
tray_icon.show()
keybinder.init()
# tooltip = Tooltip()

EXIT_KEY = "Ctrl+Alt+Q"
keybinder.register_hotkey(window.winId(), EXIT_KEY, window.close)
anki_hotkeys = register_keys()

win_event_filter = WinEventFilter(keybinder)
event_dispatcher = QAbstractEventDispatcher.instance()
event_dispatcher.installNativeEventFilter(win_event_filter)

app.exec()
unregister_keys(anki_hotkeys)
keybinder.unregister_hotkey(window.winId(), EXIT_KEY)
sct.close()
