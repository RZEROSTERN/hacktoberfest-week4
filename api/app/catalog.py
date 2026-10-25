"""The vision models tested for this app (see docs/BENCHMARKS.md), and model-name checks.

Only models that were actually measured appear here. `gemma4:e2b` was tested and deliberately
left out: it missed a sensitive screenshot, which is a safety gate rather than a quality score,
so it is not offered at any size. Anything not on this list is still reachable through the
wizard's advanced option, which is why `validate_model_name` exists.
"""

import re
from pathlib import Path

from pydantic import BaseModel


class VisionModel(BaseModel):
    model: str  # the Ollama tag
    title: str
    recommended: bool  # exactly one is the default
    size_bytes: int
    size_exact: bool  # false when the size is the rounded figure Ollama shows in its list
    ram_gb: int  # memory the computer should have; smaller machines see "not recommended"
    max_image_px: int  # the downscale size this model was measured at
    license: str
    note: str


class Catalog(BaseModel):
    version: int
    updated: str
    source: str
    vision: list[VisionModel]

    @property
    def recommended(self) -> VisionModel:
        return next(m for m in self.vision if m.recommended)

    def find(self, model: str) -> VisionModel | None:
        return next((m for m in self.vision if m.model == model), None)


def default_catalog_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "models.json"


def load_catalog(path: Path | None = None) -> Catalog:
    return Catalog.model_validate_json((path or default_catalog_path()).read_text("utf-8"))


class ModelNameError(Exception):
    """A model name the app refuses before asking Ollama; `code` is a stable error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# [host/][namespace/]name[:tag], as in the Ollama library (e.g. `gemma4:e4b` or `user/model:q4`).
_NAME = re.compile(
    r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*){0,3}(:[a-z0-9][a-z0-9._-]*)?$", re.IGNORECASE
)
# Ollama's cloud models (`gemma4:cloud`, `qwen3-vl:235b-cloud`) run on its servers, not here.
_CLOUD = re.compile(r"(^|[-_.:/])cloud($|[-_.:/])", re.IGNORECASE)


def validate_model_name(name: str) -> str:
    """Return the cleaned name, or raise ModelNameError. Ollama checks that the model exists."""
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 200 or not _NAME.match(cleaned):
        raise ModelNameError("invalid_model_name")
    if _CLOUD.search(cleaned):
        raise ModelNameError("cloud_model")
    return cleaned
