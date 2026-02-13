from __future__ import annotations

import asyncio
import json

import pytest

from lib.storage import RunStorage


def test_generate_run_id_does_not_create_placeholder_file(tmp_path) -> None:
    storage = RunStorage(str(tmp_path))

    run_id = asyncio.run(storage.generate_run_id("model/name"))

    assert run_id == "modelname-001"
    assert not (tmp_path / f"{run_id}.json").exists()


def test_save_run_prevents_overwrite_when_disabled(tmp_path) -> None:
    storage = RunStorage(str(tmp_path))
    run_id = "model-001"
    run_data = {
        "runId": run_id,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }

    asyncio.run(storage.save_run(run_id, run_data, allow_overwrite=False))

    with pytest.raises(FileExistsError):
        asyncio.run(storage.save_run(run_id, run_data, allow_overwrite=False))

    stored = json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))
    assert stored["runId"] == run_id


def test_save_run_allows_explicit_overwrite(tmp_path) -> None:
    storage = RunStorage(str(tmp_path))
    run_id = "model-001"

    asyncio.run(
        storage.save_run(
            run_id,
            {"runId": run_id, "timestamp": "2026-01-01T00:00:00+00:00", "value": 1},
            allow_overwrite=False,
        )
    )
    asyncio.run(
        storage.save_run(
            run_id,
            {"runId": run_id, "timestamp": "2026-01-01T00:00:00+00:00", "value": 2},
            allow_overwrite=True,
        )
    )

    stored = json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))
    assert stored["value"] == 2
