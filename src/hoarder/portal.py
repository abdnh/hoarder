"""Minimal client for XDG desktop portals, using jeepney.

QtDBus can't marshal some portal argument types (e.g. `a(sa{sv})`) from Python, so
portal calls go through jeepney instead. A connection isn't thread-safe; use one per thread.
"""

from __future__ import annotations

import itertools
import os
import sys
from pathlib import Path
from typing import Any

APP_ID = "net.abdnh.hoarder"
BUS_NAME = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"

_tokens = itertools.count()


class PortalError(Exception):
    pass


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


class PortalConnection:
    def __init__(self) -> None:
        from jeepney.bus_messages import message_bus
        from jeepney.io.blocking import Proxy, open_dbus_connection

        self.conn = open_dbus_connection(bus="SESSION")
        self.bus = Proxy(message_bus, self.conn)
        self.sender = self.conn.unique_name[1:].replace(".", "_")
        # Lets the portal identify us when not running in a sandbox (xdg-desktop-portal >= 1.19).
        # This must happen before any other portal call on the connection.
        ensure_desktop_file()
        try:
            self.call(
                "org.freedesktop.host.portal.Registry",
                "Register",
                "sa{sv}",
                (APP_ID, {}),
            )
        except PortalError:
            pass

    def close(self) -> None:
        self.conn.close()

    def new_token(self) -> str:
        return f"hoarder_{os.getpid()}_{next(_tokens)}"

    def call(
        self,
        interface: str,
        method: str,
        signature: str = "",
        body: tuple = (),
        path: str = PATH,
    ) -> Any:
        from jeepney import DBusAddress, MessageType, new_method_call

        msg = new_method_call(
            DBusAddress(path, BUS_NAME, interface), method, signature, body
        )
        reply = self.conn.send_and_get_reply(msg)
        if reply.header.message_type == MessageType.error:
            raise PortalError(f"{method}: {reply.body[0] if reply.body else ''}")
        return reply.body

    def request(
        self,
        interface: str,
        method: str,
        signature: str,
        body: tuple,
        token: str,
        timeout: float | None = None,
    ) -> dict:
        """Call a method that returns a Request handle and wait for its Response.

        `token` must be the `handle_token` passed in the method's options.
        """
        from jeepney import MatchRule

        # Subscribe to the Response before calling to avoid missing it
        rule = MatchRule(
            type="signal",
            interface="org.freedesktop.portal.Request",
            member="Response",
            path=f"{PATH}/request/{self.sender}/{token}",
        )
        self.bus.AddMatch(rule)
        try:
            with self.conn.filter(rule) as queue:
                self.call(interface, method, signature, body)
                response, results = self.conn.recv_until_filtered(
                    queue, timeout=timeout
                ).body
        finally:
            self.bus.RemoveMatch(rule)
        if response != 0:
            raise PortalError(f"{method} was cancelled or failed ({response})")
        return results
