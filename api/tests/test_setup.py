import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.engine import Engine

from app.catalog import load_catalog
from app.compat import CompatError
from app.db import make_engine
from app.models import SetupState
from app.ollama import InstalledModel, OllamaError
from app.settings_store import VISION_MODEL, compat_key, get_setting
from app.setup import SetupError, SetupManager

REAL = "qwen3-vl:2b-instruct"


class FakeOllama:
    """An engine whose pull can be made slow, failing, or cancellable."""

    def __init__(
        self,
        installed: list[InstalledModel] | None = None,
        reachable: bool = True,
        pull_bytes: int = 1_000_000,
        chunk_delay: float = 0.0,
        fail: OllamaError | None = None,
        becomes: InstalledModel | None = None,
    ) -> None:
        self._installed = list(installed or [])
        self._reachable = reachable
        self._pull_bytes = pull_bytes
        self._chunk_delay = chunk_delay
        self._fail = fail
        self._becomes = becomes
        self.pulled: list[str] = []
        self.deleted: list[str] = []

    def reachable(self) -> bool:
        return self._reachable

    def list_models(self) -> list[InstalledModel]:
        return list(self._installed)

    def installed(self, name: str) -> InstalledModel | None:
        wanted = name if ":" in name else f"{name}:latest"
        return next((m for m in self._installed if m.name in (name, wanted)), None)

    def delete(self, name: str) -> None:
        self.deleted.append(name)
        self._installed = [m for m in self._installed if m.name != name]

    def pull(
        self, name: str, on_progress: Callable[[int, int], None], cancel: threading.Event
    ) -> None:
        if self._fail:
            raise self._fail
        self.pulled.append(name)
        steps = 10
        for i in range(1, steps + 1):
            from app.errors import Cancelled

            if cancel.is_set():
                raise Cancelled
            if self._chunk_delay:
                time.sleep(self._chunk_delay)
            on_progress(self._pull_bytes * i // steps, self._pull_bytes)
        self._installed.append(self._becomes or InstalledModel(name, self._pull_bytes, None))


class FakeCompat:
    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.checked: list[str] = []

    def check(self, model: str, cancel: threading.Event) -> None:
        self.checked.append(model)
        if self.error:
            raise CompatError(self.error)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    data = tmp_path / "data"
    data.mkdir()
    return make_engine(data)


def manager(
    engine: Engine,
    ollama: FakeOllama,
    compat: FakeCompat | None = None,
    tmp_path: Path | None = None,
) -> SetupManager:
    return SetupManager(
        engine,
        load_catalog(),
        ollama,
        compat or FakeCompat(),
        ThreadPoolExecutor(max_workers=1),
        tmp_path or Path("."),
    )


def wait_until_settled(m: SetupManager, timeout: float = 10) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap: dict[str, Any] = m.snapshot()
        if snap["state"] != SetupState.RUNNING:
            return snap
        time.sleep(0.02)
    raise AssertionError("setup never settled")


class TestADownload:
    def test_downloads_checks_and_selects_the_model(self, engine: Engine) -> None:
        ollama, compat = FakeOllama(), FakeCompat()
        m = manager(engine, ollama, compat)
        m.start(REAL)
        snap = wait_until_settled(m)

        assert snap["state"] == SetupState.DONE
        assert ollama.pulled == [REAL]
        assert compat.checked == [REAL]
        # Only now is the model the one the app uses.
        assert get_setting(engine, VISION_MODEL) == REAL
        assert get_setting(engine, compat_key(REAL)) == "1"
        assert snap["overall"]["fraction"] == 1.0

    def test_a_model_already_here_is_not_downloaded_again(self, engine: Engine) -> None:
        ollama = FakeOllama(installed=[InstalledModel(REAL, 1_900_000_000, None)])
        m = manager(engine, ollama)
        m.start(REAL)
        snap = wait_until_settled(m)

        assert ollama.pulled == []
        step = next(s for s in snap["steps"] if s["id"] == "model")
        assert step["skipped"] is True
        assert snap["state"] == SetupState.DONE

    def test_progress_carries_size_speed_and_time_left(self, engine: Engine) -> None:
        # A model the catalog does not know, so the size comes from the download itself
        # rather than from the recorded figure.
        ollama = FakeOllama(pull_bytes=50_000_000, chunk_delay=0.02)
        m = manager(engine, ollama)
        m.start("someone/custom-vl:q4")

        seen_running = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            snap = m.snapshot()
            step = next(s for s in snap["steps"] if s["id"] == "model")
            if step["state"] == "running" and step["completed"] > 0 and step["speed_bps"]:
                seen_running = step
                break
            time.sleep(0.01)
        wait_until_settled(m)

        assert seen_running is not None, "never saw the download in progress"
        assert seen_running["total"] == 50_000_000
        assert seen_running["speed_bps"] > 0
        assert seen_running["eta_s"] is not None


class TestPauseAndResume:
    def test_pausing_keeps_what_arrived_and_resuming_finishes(self, engine: Engine) -> None:
        ollama = FakeOllama(pull_bytes=10_000_000, chunk_delay=0.05)
        m = manager(engine, ollama)
        m.start(REAL)

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            step = next(s for s in m.snapshot()["steps"] if s["id"] == "model")
            if step["completed"] > 0:
                break
            time.sleep(0.01)
        m.pause()
        paused = wait_until_settled(m)

        assert paused["state"] == SetupState.PAUSED
        assert get_setting(engine, VISION_MODEL) is None  # nothing was selected

        m.resume()
        assert wait_until_settled(m)["state"] == SetupState.DONE
        assert get_setting(engine, VISION_MODEL) == REAL

    def test_resuming_with_nothing_to_resume_is_refused(self, engine: Engine) -> None:
        m = manager(engine, FakeOllama())
        with pytest.raises(SetupError) as caught:
            m.resume()
        assert caught.value.code == "nothing_to_resume"

    def test_a_second_run_while_one_is_going_is_refused(self, engine: Engine) -> None:
        m = manager(engine, FakeOllama(pull_bytes=10_000_000, chunk_delay=0.05))
        m.start(REAL)
        with pytest.raises(SetupError) as caught:
            m.start("gemma4:e4b")
        assert caught.value.code == "setup_busy"
        m.pause()
        wait_until_settled(m)


class TestRefusals:
    def test_a_model_that_cannot_read_an_image_is_not_selected(self, engine: Engine) -> None:
        m = manager(engine, FakeOllama(), FakeCompat(error="compat_no_vision"))
        m.start("some-text-model")
        snap = wait_until_settled(m)

        assert snap["state"] == SetupState.COMPAT_FAILED
        assert snap["error_code"] == "compat_no_vision"
        # It downloaded, but it never becomes the model the app uses.
        assert get_setting(engine, VISION_MODEL) is None

    def test_a_cloud_model_is_deleted_rather_than_used(self, engine: Engine) -> None:
        # Ollama only reveals it runs elsewhere once it is installed.
        cloud = InstalledModel("something:latest", 0, "api.ollama.com")
        ollama = FakeOllama(becomes=cloud)
        m = manager(engine, ollama)
        m.start("something:latest")
        snap = wait_until_settled(m)

        assert snap["state"] == SetupState.FAILED
        assert snap["error_code"] == "cloud_model"
        assert ollama.deleted == ["something:latest"]

    def test_a_cloud_name_is_refused_before_anything_is_downloaded(self, engine: Engine) -> None:
        ollama = FakeOllama()
        m = manager(engine, ollama)
        with pytest.raises(SetupError) as caught:
            m.start("gemma4:cloud")
        assert caught.value.code == "cloud_model"
        assert ollama.pulled == []

    def test_an_unreachable_engine_fails_the_run_rather_than_hanging(self, engine: Engine) -> None:
        m = SetupManager(
            engine,
            load_catalog(),
            FakeOllama(reachable=False),
            FakeCompat(),
            ThreadPoolExecutor(max_workers=1),
            Path("."),
        )
        m._steps[0].state = "pending"
        import app.setup as setup_module

        original = setup_module.ENGINE_WAIT_SECONDS
        setup_module.ENGINE_WAIT_SECONDS = 0.2
        try:
            m.start(REAL)
            snap = wait_until_settled(m)
        finally:
            setup_module.ENGINE_WAIT_SECONDS = original
        assert snap["state"] == SetupState.FAILED
        assert snap["error_code"] == "ollama_unreachable"


class TestManagingModels:
    def test_a_model_not_checked_here_cannot_be_activated(self, engine: Engine) -> None:
        ollama = FakeOllama(installed=[InstalledModel(REAL, 1, None)])
        m = manager(engine, ollama)
        with pytest.raises(SetupError) as caught:
            m.activate(REAL)
        # Downloaded elsewhere, or by an older version: it still has to pass the image check.
        assert caught.value.code == "compat_needed"

    def test_the_model_in_use_cannot_be_deleted(self, engine: Engine) -> None:
        ollama = FakeOllama()
        m = manager(engine, ollama)
        m.start(REAL)
        wait_until_settled(m)

        with pytest.raises(SetupError) as caught:
            m.delete(REAL)
        assert caught.value.code == "model_in_use"
        assert ollama.deleted == []

    def test_status_reports_what_is_missing(self, engine: Engine) -> None:
        m = manager(engine, FakeOllama())
        before = m.status()
        assert before["ready"] is False
        assert before["model"]["state"] == "not_selected"
        assert len(before["recommended"]) >= 1

        m.start(REAL)
        wait_until_settled(m)
        after = m.status()
        assert after["ready"] is True
        assert after["model"] == {"model": REAL, "state": "ready"}
