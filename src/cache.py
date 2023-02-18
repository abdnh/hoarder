"""This module is used to cache clippings to file when AnkiConnect is not running"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from config import AnkiHotkey

CACHE_PATH = Path(__file__).parent / Path("cache.json")


@dataclasses.dataclass
class CacheEntry:
    hotkey_context: AnkiHotkey
    text: str
    screenshot_name: str


def read() -> list[CacheEntry]:
    if not CACHE_PATH.exists():
        with open(CACHE_PATH, "w", encoding="utf-8") as file:
            file.write("[]")

    entries = []
    for ent in json.loads(CACHE_PATH.read_text(encoding="utf-8")):
        entries.append(
            CacheEntry(
                hotkey_context=AnkiHotkey(**ent["hotkey_context"]),
                text=ent["text"],
                screenshot_name=ent["screenshot_name"],
            )
        )

    return entries


def write(entries: list[CacheEntry]) -> None:
    data = []
    for entry in entries:
        data.append(
            {
                "hotkey_context": dataclasses.asdict(entry.hotkey_context),
                "text": entry.text,
                "screenshot_name": entry.screenshot_name,
            }
        )
    with open(CACHE_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file)


def add(hotkey_context: AnkiHotkey, text: str, screenshot_name: str) -> None:
    entries = read()
    entries.append(
        CacheEntry(
            hotkey_context=hotkey_context, text=text, screenshot_name=screenshot_name
        )
    )
    write(entries)
