"""First-launch setup and model management: get the model, verify it, check it can read.

A run goes through five steps: prepare the engine, download the model, verify it, check it can
actually read an image, ready. A run can be paused and resumed, and one cut short by closing the
app is offered again on the next launch rather than resumed silently, because downloading
several gigabytes is the user's decision, not the app's.
"""

import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import Executor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.catalog import Catalog, ModelNameError, validate_model_name
from app.compat import CompatChecker, CompatError
from app.downloads import SpeedMeter
from app.errors import Cancelled
from app.models import SetupRun, SetupState
from app.ollama import InstalledModel, ModelEngine, OllamaError
from app.settings_store import VISION_MODEL, compat_key, delete_setting, get_setting, set_setting

log = logging.getLogger("slothshot.setup")

ENGINE_WAIT_SECONDS = 30.0
PERSIST_EVERY = 2.0

STEP_IDS = ("engine", "model", "verify", "compat", "ready")
LABELS = {
    "engine": "Preparing the local AI engine",
    "model": "Downloading the model",
    "verify": "Verifying the download",
    "compat": "Checking that it can read a screenshot",
    "ready": "Ready",
}
# How much of the overall bar each step is worth. A step with nothing to do counts as 1.
WEIGHTS = {"engine": 3, "model": 75, "verify": 2, "compat": 20, "ready": 0}


class SetupError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class Step:
    id: str
    state: str = "pending"  # pending | running | done | failed
    completed: int = 0
    total: int = 0
    detail: str | None = None
    skipped: bool = False  # nothing to do: already on this computer
    meter: SpeedMeter = field(default_factory=SpeedMeter)


class SetupManager:
    def __init__(
        self,
        engine: Engine,
        catalog: Catalog,
        ollama: ModelEngine,
        compat: CompatChecker,
        executor: Executor,
        models_dir: Path,
        free_disk: Callable[[Path], int] | None = None,
    ) -> None:
        self._engine = engine
        self.catalog = catalog
        self.ollama = ollama
        self._compat = compat
        self._executor = executor
        self._models_dir = models_dir
        self._free_disk = free_disk
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._stopping = False
        self._state = SetupState.IDLE
        self._model: str | None = None
        self._error: str | None = None
        self._fraction = 0.0
        self._steps = [Step(step_id) for step_id in STEP_IDS]
        self._last_persist = 0.0

    # -- lifecycle ----------------------------------------------------------------------------

    def recover(self) -> None:
        """Load the last run. One that was running when the app closed is now interrupted."""
        with Session(self._engine) as session:
            run = session.get(SetupRun, 1)
        if run is None:
            return
        self._model, self._error, self._fraction = (
            run.model_tag,
            run.error_code,
            run.overall_fraction,
        )
        self._state = SetupState.INTERRUPTED if run.state == SetupState.RUNNING else run.state
        if run.steps:
            self._steps = [
                Step(
                    s["id"],
                    s["state"],
                    s["completed"],
                    s["total"],
                    s.get("detail"),
                    s.get("skipped", False),
                )
                for s in run.steps
            ]
        self._persist()

    def stop(self) -> None:
        self._stopping = True
        self._cancel.set()

    def start(self, model: str) -> None:
        """Begin a run for `model` (first launch, a switch, or a new download)."""
        try:
            name = validate_model_name(model)
        except ModelNameError as exc:
            raise SetupError(exc.code) from exc
        with self._lock:
            if self._state == SetupState.RUNNING:
                raise SetupError("setup_busy")
            keep = self._fraction if name == self._model and self._state != SetupState.DONE else 0.0
            self._begin(name, keep)
        self._executor.submit(self._run, name)

    def resume(self) -> None:
        with self._lock:
            if self._state == SetupState.RUNNING:
                raise SetupError("setup_busy")
            if self._state == SetupState.DONE or self._model is None:
                raise SetupError("nothing_to_resume")
            name = self._model
            self._begin(name, self._fraction)
        self._executor.submit(self._run, name)

    def pause(self) -> None:
        if self._state == SetupState.RUNNING:
            self._cancel.set()

    def _begin(self, name: str, keep_fraction: float) -> None:
        self._cancel = threading.Event()
        self._model, self._error, self._state = name, None, SetupState.RUNNING
        self._fraction = keep_fraction
        self._steps = [Step(step_id) for step_id in STEP_IDS]
        self._persist()

    # -- the run ------------------------------------------------------------------------------

    def _run(self, model: str) -> None:
        cancel = self._cancel
        try:
            self._pipeline(model, cancel)
            self._finish(SetupState.DONE)
        except Cancelled:
            self._finish(SetupState.INTERRUPTED if self._stopping else SetupState.PAUSED)
        except CompatError as exc:
            self._finish(SetupState.COMPAT_FAILED, exc.code, fail_step="compat")
        except (OllamaError, SetupError) as exc:
            self._finish(SetupState.FAILED, exc.code)
        except Exception:
            log.exception("unexpected failure in the model setup")
            self._finish(SetupState.FAILED, "setup_failed")

    def _pipeline(self, model: str, cancel: threading.Event) -> None:
        self._plan(model)

        # 1. the engine
        self._begin_step("engine")
        deadline = time.monotonic() + ENGINE_WAIT_SECONDS
        while not self.ollama.reachable():
            if cancel.is_set():
                raise Cancelled
            if time.monotonic() > deadline:
                raise SetupError("ollama_unreachable")
            cancel.wait(1)
        self._end_step("engine")

        # 2. the model
        installed = self.ollama.installed(model)
        self._require_local(installed)
        known = self.catalog.find(model)
        if installed:
            self._end_step("model", skipped=True, detail="Already on this computer")
        else:
            self._begin_step("model", detail=model, total=known.size_bytes if known else 0)
            self.ollama.pull(model, lambda c, t: self._progress("model", c, t), cancel)
            installed = self.ollama.installed(model)
            if installed is None:
                raise SetupError("model_not_installed")
            if installed.remote_host:  # a cloud model after all: remove it, never use it
                self.ollama.delete(model)
                raise SetupError("cloud_model")
            self._end_step("model")

        # 3. verify
        self._begin_step("verify")
        if self.ollama.installed(model) is None:
            raise SetupError("model_not_installed")
        self._end_step("verify")

        # 4. can it actually read an image?
        self._begin_step("compat", detail=model)
        self._compat.check(model, cancel)
        set_setting(self._engine, VISION_MODEL, model)
        set_setting(self._engine, compat_key(model), "1")
        self._end_step("compat")
        self._end_step("ready")

    @staticmethod
    def _require_local(model: InstalledModel | None) -> None:
        if model is not None and model.remote_host:
            raise SetupError("cloud_model")

    def _plan(self, model: str) -> None:
        """Mark steps that will have nothing to do, so the overall bar does not jump later."""
        try:
            installed = self.ollama.installed(model) is not None
        except OllamaError:
            installed = False
        with self._lock:
            self._step("model").skipped = installed
            self._update_fraction()

    # -- progress bookkeeping -----------------------------------------------------------------

    def _step(self, step_id: str) -> Step:
        return next(s for s in self._steps if s.id == step_id)

    def _begin_step(self, step_id: str, detail: str | None = None, total: int = 0) -> None:
        with self._lock:
            step = self._step(step_id)
            step.state, step.detail, step.total = "running", detail, total
            step.completed, step.skipped = 0, False
            self._update_fraction()
            self._persist()

    def _end_step(self, step_id: str, skipped: bool = False, detail: str | None = None) -> None:
        with self._lock:
            step = self._step(step_id)
            step.state, step.skipped = "done", skipped
            if detail:
                step.detail = detail
            if not skipped and step.total:
                step.completed = step.total
            self._update_fraction()
            self._persist()

    def _progress(self, step_id: str, completed: int, total: int) -> None:
        with self._lock:
            step = self._step(step_id)
            step.completed = max(step.completed, completed)  # the bar never moves backwards
            step.total = max(step.total, total)
            step.meter.add(step.completed)
            self._update_fraction()
            if time.monotonic() - self._last_persist >= PERSIST_EVERY:
                self._persist()

    def _update_fraction(self) -> None:
        weight_sum = gained = 0.0
        for step in self._steps:
            weight = 1.0 if step.skipped else float(WEIGHTS[step.id])
            if step.state == "done":
                part = 1.0
            elif step.state == "running":
                part = step.completed / step.total if step.total else 0.5
            else:
                part = 0.0
            weight_sum += weight
            gained += weight * part
        if weight_sum:
            self._fraction = max(self._fraction, min(gained / weight_sum, 0.999))

    def _finish(
        self, state: SetupState, error: str | None = None, fail_step: str | None = None
    ) -> None:
        with self._lock:
            self._state, self._error = state, error
            if state == SetupState.DONE:
                self._fraction = 1.0
            if state in (SetupState.FAILED, SetupState.COMPAT_FAILED):
                for step in self._steps:
                    if step.state == "running" or step.id == fail_step:
                        step.state = "failed"
            self._persist()

    def _persist(self) -> None:
        self._last_persist = time.monotonic()
        steps: list[dict[str, Any]] = [
            {
                "id": s.id,
                "state": s.state,
                "completed": s.completed,
                "total": s.total,
                "detail": s.detail,
                "skipped": s.skipped,
            }
            for s in self._steps
        ]
        with Session(self._engine) as session:
            run = session.get(SetupRun, 1) or SetupRun(id=1)
            run.state, run.model_tag, run.steps = self._state, self._model, steps
            run.overall_fraction, run.error_code = self._fraction, self._error
            run.updated_at = datetime.now(UTC)
            session.add(run)
            session.commit()

    # -- reading state ------------------------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        """Everything the progress screen shows, as plain data."""
        with self._lock:
            steps = []
            for s in self._steps:
                remaining = max(s.total - s.completed, 0)
                running = s.state == "running" and s.total > 0
                steps.append(
                    {
                        "id": s.id,
                        "label": LABELS[s.id],
                        "state": s.state,
                        "detail": s.detail,
                        "skipped": s.skipped,
                        "completed": s.completed,
                        "total": s.total,
                        "speed_bps": s.meter.speed() if running else None,
                        "eta_s": s.meter.eta(remaining) if running else None,
                    }
                )
            download = self._step("model")
            return {
                "state": self._state,
                "model": self._model,
                "steps": steps,
                "error_code": self._error,
                "overall": {
                    "fraction": self._fraction,
                    "completed_bytes": 0 if download.skipped else download.completed,
                    "total_bytes": 0 if download.skipped else download.total,
                },
            }

    def active_model(self) -> str | None:
        return get_setting(self._engine, VISION_MODEL)

    def status(self) -> dict[str, Any]:
        """Is the app ready to use, and if not, what is missing?"""
        reachable = self.ollama.reachable()
        active = self.active_model()
        installed = self.ollama.installed(active) if reachable and active else None
        model_ready = installed is not None and installed.remote_host is None
        compat_ok = bool(active) and get_setting(self._engine, compat_key(active or "")) == "1"
        model_state = "not_selected" if not active else ("ready" if model_ready else "missing")
        with self._lock:
            partial = self._state in (
                SetupState.PAUSED,
                SetupState.FAILED,
                SetupState.INTERRUPTED,
            ) and any(s.completed > 0 for s in self._steps)
            run = {"state": self._state, "model": self._model, "fraction": self._fraction}
        if partial and model_state != "ready" and run["model"] is not None:
            model_state = "partial"
        return {
            "ready": reachable and model_ready and compat_ok,
            "ollama_reachable": reachable,
            "model": {"model": active, "state": model_state},
            "compat_ok": compat_ok,
            "run": run,
            "recommended": [m.model_dump() for m in self.catalog.vision],
        }

    # -- managing models ----------------------------------------------------------------------

    def models(self) -> list[dict[str, Any]]:
        """The models on this computer, with what the app knows about each."""
        active = self.active_model()
        out = []
        for model in self.ollama.list_models():
            info = self.catalog.find(model.name)
            out.append(
                {
                    "name": model.name,
                    "size_bytes": model.size_bytes,
                    "cloud": model.remote_host is not None,
                    "active": model.name == active,
                    "compat_ok": get_setting(self._engine, compat_key(model.name)) == "1",
                    "catalog": info.model_dump() if info else None,
                }
            )
        return out

    def activate(self, model: str) -> None:
        installed = self.ollama.installed(model)
        if installed is None:
            raise SetupError("model_not_installed")
        self._require_local(installed)
        if get_setting(self._engine, compat_key(installed.name)) != "1":
            # Not checked on this computer yet: run the setup for it, which ends in the check.
            raise SetupError("compat_needed")
        set_setting(self._engine, VISION_MODEL, installed.name)

    def delete(self, model: str) -> None:
        if self._state == SetupState.RUNNING:
            raise SetupError("setup_busy")
        installed = self.ollama.installed(model)
        if installed is None:
            raise SetupError("model_not_installed")
        if installed.name == self.active_model():
            raise SetupError("model_in_use")
        self.ollama.delete(installed.name)
        delete_setting(self._engine, compat_key(installed.name))
