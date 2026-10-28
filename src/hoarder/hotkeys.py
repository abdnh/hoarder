from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

APP_ID = "net.abdnh.hoarder"


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


PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"


def ensure_desktop_file() -> None:
    """Install a minimal desktop file if none exists; the portal refuses to register app IDs without one."""
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    dirs = [data_home] + [Path(d) for d in data_dirs.split(":") if d]
    if any((d / "applications" / f"{APP_ID}.desktop").exists() for d in dirs):
        return
    path = data_home / "applications" / f"{APP_ID}.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Hoarder\n"
        "Comment=Helper for copying text to Anki\n"
        f"Exec={sys.executable} -m hoarder\n"
        "NoDisplay=true\n",
        encoding="utf-8",
    )


class PortalHotkeyBackend(HotkeyBackend):
    """Uses the XDG desktop portal GlobalShortcuts interface (works on Wayland without root).

    QtDBus can't marshal the `a(sa{sv})` argument of BindShortcuts from Python, so this
    talks to the portal with jeepney on a worker thread instead.
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
        from jeepney import DBusAddress, MatchRule, MessageType, new_method_call
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import Proxy, open_dbus_connection

        conn = open_dbus_connection(bus="SESSION")
        bus = Proxy(message_bus, conn)
        sender = conn.unique_name[1:].replace(".", "_")
        portal = DBusAddress(PORTAL_PATH, PORTAL_BUS_NAME)

        def call(interface: str, method: str, signature: str, body: tuple) -> Any:
            msg = new_method_call(
                portal.with_interface(interface), method, signature, body
            )
            reply = conn.send_and_get_reply(msg)
            if reply.header.message_type == MessageType.error:
                raise RuntimeError(f"{method}: {reply.body[0] if reply.body else ''}")
            return reply.body

        def request(method: str, signature: str, body: tuple, token: str) -> dict:
            # Subscribe to the Response before calling to avoid missing it
            rule = MatchRule(
                type="signal",
                interface="org.freedesktop.portal.Request",
                member="Response",
                path=f"{PORTAL_PATH}/request/{sender}/{token}",
            )
            bus.AddMatch(rule)
            with conn.filter(rule) as queue:
                call("org.freedesktop.portal.GlobalShortcuts", method, signature, body)
                response, results = conn.recv_until_filtered(queue).body
            bus.RemoveMatch(rule)
            if response != 0:
                raise RuntimeError(f"{method} was cancelled or failed ({response})")
            return results

        # Lets the portal identify us when not running in a sandbox (xdg-desktop-portal >= 1.19)
        ensure_desktop_file()
        try:
            call(
                "org.freedesktop.host.portal.Registry",
                "Register",
                "sa{sv}",
                (APP_ID, {}),
            )
        except RuntimeError:
            pass

        results = request(
            "CreateSession",
            "a{sv}",
            (
                {
                    "handle_token": ("s", "hoarder_session"),
                    "session_handle_token": ("s", "hoarder"),
                },
            ),
            "hoarder_session",
        )
        session = results["session_handle"][1]

        activated = MatchRule(
            type="signal",
            interface="org.freedesktop.portal.GlobalShortcuts",
            member="Activated",
            path=PORTAL_PATH,
        )
        activated.add_arg_condition(0, session)
        bus.AddMatch(activated)
        with conn.filter(activated) as queue:
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
            request(
                "BindShortcuts",
                "oa(sa{sv})sa{sv}",
                (session, shortcuts, "", {"handle_token": ("s", "hoarder_bind")}),
                "hoarder_bind",
            )
            while not self._stopping.is_set():
                try:
                    msg = conn.recv_until_filtered(queue, timeout=0.5)
                except TimeoutError:
                    continue
                self.activated.emit(msg.body[1])

        conn.send(
            new_method_call(
                DBusAddress(session, PORTAL_BUS_NAME, "org.freedesktop.portal.Session"),
                "Close",
            )
        )
        conn.close()


def create_backend() -> HotkeyBackend:
    if sys.platform == "linux":
        return PortalHotkeyBackend()
    return KeyboardHotkeyBackend()
