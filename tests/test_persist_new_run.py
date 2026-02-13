from __future__ import annotations

import asyncio
import importlib
from typing import Any


class DummyStorage:
    def __init__(self) -> None:
        self._id_counter = 0
        self.save_calls: list[tuple[str, dict[str, Any], bool]] = []

    async def generate_run_id(self, _model_name: str) -> str:
        self._id_counter += 1
        return f"model-{self._id_counter:03d}"

    async def save_run(
        self,
        run_id: str,
        run_data: dict[str, Any],
        allow_overwrite: bool = True,
    ) -> None:
        self.save_calls.append((run_id, dict(run_data), allow_overwrite))
        if len(self.save_calls) < 3:
            raise FileExistsError("simulated collision")


def test_persist_new_run_retries_with_backoff(monkeypatch) -> None:
    main = importlib.import_module("main")
    storage = DummyStorage()
    run_data: dict[str, Any] = {"modelName": "test/model"}
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(main.random, "uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr(main.asyncio, "sleep", fake_sleep)

    run_id = asyncio.run(main._persist_new_run(storage, "test/model", run_data, max_attempts=5))

    assert run_id == "model-003"
    assert run_data["runId"] == "model-003"
    assert len(storage.save_calls) == 3
    assert all(call[2] is False for call in storage.save_calls)
    assert delays == [0.02, 0.04]

