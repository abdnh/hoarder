import os
import json
import urllib.request


def request(action, **params):
    return {"action": action, "params": params, "version": 6}


def invoke(action, **params):
    requestJson = json.dumps(request(action, **params)).encode("utf-8")
    response = json.load(
        urllib.request.urlopen(
            urllib.request.Request("http://127.0.0.1:8765", requestJson)
        )
    )
    if len(response) != 2:
        raise Exception("response has an unexpected number of fields")
    if "error" not in response:
        raise Exception("response is missing required error field")
    if "result" not in response:
        raise Exception("response is missing required result field")
    if response["error"] is not None:
        raise Exception(response["error"])
    return response["result"]


def add_note(
    notetype: str,
    deck: str,
    field: str,
    contents: str,
    screenshot_field: str,
    screenshot_filename: str,
    refs: str = "",
) -> int:
    note = {
        "deckName": deck,
        "modelName": notetype,
        "fields": {
            field: contents,
            "Back": "",
            "References": refs,
        },
        "options": {
            "allowDuplicate": True,
            "duplicateScope": "deck",
            "duplicateScopeOptions": {
                "deckName": None,
                "checkChildren": True,
            },
        },
        "picture": [
            {
                "filename": screenshot_filename,
                "path": os.path.join(os.path.dirname(__file__), screenshot_filename),
                "deleteExisting": False,
                "fields": [screenshot_field],
            }
        ],
    }

    return invoke("addNote", note=note)


def store_media(path: str):
    invoke(
        "storeMediaFile",
        filename=path,
        path=path,
        deleteExisting=False,
    )
