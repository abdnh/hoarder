from __future__ import annotations

import sys
import threading
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class Hotkey:
    # Stable ID; the desktop remembers user rebindings by it
    id: str
    # Trigger in `keyboard` format, e.g. "Ctrl+Alt+O"
    trigger: str
    description: str


class HotkeyBackend(QObject):
    """Registers global hotkeys and emits `activated` with the hotkey ID on the main thread."""

    activated = pyqtSignal(str)
    failed = pyqtSignal(str)

    def start(self, hotkeys: list[Hotkey]) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class KeyboardHotkeyBackend(HotkeyBackend):
    """Uses the `keyboard` package (requires root on Linux)."""

    def start(self, hotkeys: list[Hotkey]) -> None:
        import keyboard

        self._triggers = [hotkey.trigger for hotkey in hotkeys]
        for hotkey in hotkeys:
            keyboard.register_hotkey(
                hotkey.trigger, lambda id=hotkey.id: self.activated.emit(id)
            )

    def stop(self) -> None:
        import keyboard

        for trigger in self._triggers:
            keyboard.remove_hotkey(trigger)


MODIFIERS = {
    "ctrl": "CTRL",
    "control": "CTRL",
    "alt": "ALT",
    "shift": "SHIFT",
    "win": "LOGO",
    "windows": "LOGO",
    "super": "LOGO",
    "meta": "LOGO",
    "cmd": "LOGO",
}

KEYSYMS = {
    "enter": "Return",
    "return": "Return",
    "space": "space",
    "esc": "Escape",
    "escape": "Escape",
    "tab": "Tab",
    "backspace": "BackSpace",
    "delete": "Delete",
}


def to_portal_trigger(trigger: str) -> str:
    """Convert e.g. "Ctrl+Alt+O" to the XDG shortcuts format "CTRL+ALT+o"."""
    parts = []
    for part in trigger.split("+"):
        part = part.strip()
        lower = part.lower()
        if lower in MODIFIERS:
            parts.append(MODIFIERS[lower])
        elif lower in KEYSYMS:
            parts.append(KEYSYMS[lower])
        elif len(part) == 1:
            parts.append(lower)
        else:
            parts.append(part)
    return "+".join(parts)


class PortalHotkeyBackend(HotkeyBackend):
    """Uses the XDG desktop portal GlobalShortcuts interface (works on Wayland without root).

    Runs on a worker thread with its own portal connection, since the connection blocks.
    """

    def __init__(self) -> None:
        super().__init__()
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()

    def start(self, hotkeys: list[Hotkey]) -> None:
        self._thread = threading.Thread(
            target=self._run, args=(hotkeys,), name="portal-hotkeys", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self, hotkeys: list[Hotkey]) -> None:
        try:
            self._listen(hotkeys)
        except Exception as exc:
            self.failed.emit(f"Failed to register global shortcuts: {exc}")

    def _listen(self, hotkeys: list[Hotkey]) -> None:
        from jeepney import MatchRule

        from hoarder import portal

        interface = "org.freedesktop.portal.GlobalShortcuts"
        conn = portal.PortalConnection()
        token = conn.new_token()
        results = conn.request(
            interface,
            "CreateSession",
            "a{sv}",
            (
                {
                    "handle_token": ("s", token),
                    "session_handle_token": ("s", conn.new_token()),
                },
            ),
            token,
        )
        session = results["session_handle"][1]

        activated = MatchRule(
            type="signal", interface=interface, member="Activated", path=portal.PATH
        )
        activated.add_arg_condition(0, session)
        conn.bus.AddMatch(activated)
        with conn.conn.filter(activated) as queue:
            shortcuts = [
                (
                    hotkey.id,
                    {
                        "description": ("s", hotkey.description),
                        "preferred_trigger": ("s", to_portal_trigger(hotkey.trigger)),
                    },
                )
                for hotkey in hotkeys
            ]
            token = conn.new_token()
            conn.request(
                interface,
                "BindShortcuts",
                "oa(sa{sv})sa{sv}",
                (session, shortcuts, "", {"handle_token": ("s", token)}),
                token,
            )
            while not self._stopping.is_set():
                try:
                    msg = conn.conn.recv_until_filtered(queue, timeout=0.5)
                except TimeoutError:
                    continue
                self.activated.emit(msg.body[1])

        conn.call("org.freedesktop.portal.Session", "Close", path=session)
        conn.close()


def create_backend() -> HotkeyBackend:
    if sys.platform == "linux":
        return PortalHotkeyBackend()
    return KeyboardHotkeyBackend()
