import re
from pathlib import Path

import polib

from resources.lib.language import Language

_ADDON_DIR = Path(__file__).resolve().parents[1]


def load_strings() -> tuple[dict[int, str], dict[int, str]]:
    builtins = {
        128: "General",
        137: "Search",
        733: "Password",
        1024: "Browse",
        10038: "Advanced",
        13362: "Continue watching",
        14086: "Playback",
        14280: "Maintenance",
        19265: "The entered PIN was incorrect.",
        19335: "New search...",
        20126: "Log off",
        20191: "Enable debug logging",
        21417: "Settings",
        29911: "EMail",
    }

    strings_file = _ADDON_DIR / "resources/language/resource.language.en_gb/strings.po"

    entries = polib.pofile(str(strings_file))
    return builtins, {int(entry.msgctxt.removeprefix("#")): entry.msgstr or entry.msgid for entry in entries}


def _python_ids() -> dict[str, int]:
    ids = {name: uid for name, uid in vars(Language).items() if name.isupper() and isinstance(uid, int)}
    assert len(ids) > 10, "No text IDs found in strings"
    return ids


def _settings_ids() -> set[int]:
    settings = (_ADDON_DIR / "resources/settings.xml").read_text()
    found = re.findall(r'(?:label|help)="(\d+)"|<heading>(\d+)</heading>', settings)
    assert len(found) > 0, "No labels found in settings.xml"
    return {int(uid) for pair in found for uid in pair if uid}


def _all_ids() -> tuple[set[int], dict[int, str]]:
    pids = _python_ids()
    rpids = {uid: name for name, uid in pids.items()}
    ids = set(pids.values()) | _settings_ids()
    return ids, rpids


def test_every_string_is_translated() -> None:
    all_strs = load_strings()
    strings = {**all_strs[0], **all_strs[1]}
    ids, rpids = _all_ids()
    untranslated = [rpids.get(uid, str(uid)) for uid in ids if uid not in strings]
    assert untranslated == []
