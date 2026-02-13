from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from lib.capabilities import clear_capability_cache, load_capabilities


def _capability_entry(capability_id: str, title: str) -> dict[str, object]:
    return {
        "id": capability_id,
        "title": title,
        "type": "capability",
        "category": "Reasoning",
        "promptTemplate": "Reply YES",
        "evaluation": {
            "required": [r"\AYES\Z"],
            "forbidden": [],
            "pass_threshold": 1.0,
        },
    }


def _write_capabilities(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(entries), encoding="utf-8")


def test_load_capabilities_rejects_duplicate_ids(tmp_path: Path) -> None:
    caps_path = tmp_path / "caps.json"
    _write_capabilities(
        caps_path,
        [
            _capability_entry("dup-id", "One"),
            _capability_entry("dup-id", "Two"),
        ],
    )

    clear_capability_cache()
    try:
        with pytest.raises(ValueError, match="Duplicate capability ID"):
            load_capabilities(caps_path)
    finally:
        clear_capability_cache()


def test_load_capabilities_refreshes_when_file_changes(tmp_path: Path) -> None:
    caps_path = tmp_path / "caps.json"
    _write_capabilities(caps_path, [_capability_entry("cap-1", "First Title")])

    clear_capability_cache()
    try:
        first = load_capabilities(caps_path)
        assert first[0]["title"] == "First Title"

        _write_capabilities(caps_path, [_capability_entry("cap-1", "Updated Title")])
        current_stat = caps_path.stat()
        os.utime(caps_path, (current_stat.st_atime + 1, current_stat.st_mtime + 1))

        second = load_capabilities(caps_path)
        assert second[0]["title"] == "Updated Title"
    finally:
        clear_capability_cache()

