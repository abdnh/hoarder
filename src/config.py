import json
import os
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class AnkiHotkey:
    hotkey: str
    notetype: str
    deck: str
    target_field: str
    screenshot_field: str


def read_config() -> List[AnkiHotkey]:
    with open(
        os.path.join(os.path.dirname(__file__), "config.json"), encoding="utf-8"
    ) as file:
        items: List[Dict] = json.load(file)
    anki_hotkeys = []
    for item in items:
        anki_hotkeys.append(AnkiHotkey(**item))
    return anki_hotkeys
