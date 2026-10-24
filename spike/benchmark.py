"""Model spike: compares vision models on the sample screenshots.

Measures, per model and per downscale size:
  - seconds per screenshot (Ollama's own total_duration, so transport is excluded)
  - peak resident memory of the Ollama processes while the run is going
  - category accuracy against the expected labels
  - sensitive-flag accuracy, counted both ways (a miss matters far more than a false alarm)
  - how often the answer had to be retried or was unusable

Run it on any machine with Ollama and the models installed:

    uv run --project ../api python benchmark.py
    uv run --project ../api python benchmark.py --models qwen3-vl:2b-instruct --sizes 1024
    uv run --project ../api python benchmark.py --set real      # local only, never committed

Results land in spike/results/<host>-<set>-<timestamp>.json and a table is printed.
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import statistics
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "api"))

import httpx  # noqa: E402
import psutil  # noqa: E402

from app.errors import ApiError  # noqa: E402
from app.images import load_for_analysis  # noqa: E402
from app.vision import PROMPT_VERSION, OllamaVision  # noqa: E402

DEFAULT_MODELS = ["qwen3-vl:2b-instruct", "gemma4:e2b", "gemma4:e4b"]
DEFAULT_SIZES = [768, 1024]
OLLAMA_URL = "http://127.0.0.1:11434"

# Targets from the build order, measured on the development Mac.
TARGET_SECONDS = 10.0
TARGET_PEAK_GB = 3.0
TARGET_CATEGORY_ACCURACY = 0.85


def loaded_models() -> list[str]:
    """Models Ollama currently holds in memory (documented: GET /api/ps)."""
    try:
        with httpx.Client(base_url=OLLAMA_URL, timeout=5) as client:
            return [m["name"] for m in client.get("/api/ps").json().get("models", [])]
    except (httpx.HTTPError, ValueError, KeyError):
        return []


def unload_all(settle: float = 30.0) -> None:
    """Unloads every resident model and waits for the memory to actually come back.

    Without this, each model's first run overlaps with the previous model still unloading
    (keep_alive is 30s), and the peak reads high for whichever run happens to go first. That
    artefact is what made 768px look more expensive than 1024px in the first measurement.

    Documented unload: a request carrying keep_alive 0.
    """
    for name in loaded_models():
        try:
            with httpx.Client(base_url=OLLAMA_URL, timeout=30) as client:
                client.post("/api/generate", json={"model": name, "keep_alive": 0})
        except httpx.HTTPError:
            pass

    deadline = time.monotonic() + settle
    while time.monotonic() < deadline:
        if not loaded_models():
            break
        time.sleep(0.5)
    time.sleep(2.0)  # the runner process takes a moment to actually exit after /api/ps clears


class OllamaMemory:
    """Samples the resident memory of every Ollama process while a run is going.

    Ollama serves from one process and spawns a runner per loaded model, so both are summed.
    RSS is a proxy: on a Mac with unified memory some of the model also sits in GPU-shared
    pages, which RSS does report, while on a discrete GPU it would not. The number is therefore
    read as "what this costs the machine's RAM", which is what the budget is about.
    """

    def __init__(self, interval: float = 0.25) -> None:
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.peak_bytes = 0
        self.baseline_bytes = 0

    @staticmethod
    def _total() -> int:
        total = 0
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                name = (proc.info["name"] or "").lower()
                if "ollama" in name or "llama-server" in name:
                    total += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return total

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self.peak_bytes = max(self.peak_bytes, self._total())

    def __enter__(self) -> OllamaMemory:
        self.baseline_bytes = self._total()
        self.peak_bytes = self.baseline_bytes
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)


@dataclass
class Row:
    file: str
    expected_category: str
    got_category: str | None
    expected_sensitive: bool
    got_sensitive: bool | None
    slug: str | None
    seconds: float
    retried: bool
    error: str | None = None


@dataclass
class RunResult:
    model: str
    size: int
    rows: list[Row] = field(default_factory=list)
    peak_bytes: int = 0
    baseline_bytes: int = 0

    @property
    def usable(self) -> list[Row]:
        return [r for r in self.rows if r.error is None]

    @property
    def seconds_median(self) -> float:
        times = [r.seconds for r in self.usable]
        return statistics.median(times) if times else 0.0

    @property
    def seconds_mean(self) -> float:
        times = [r.seconds for r in self.usable]
        return statistics.fmean(times) if times else 0.0

    @property
    def category_accuracy(self) -> float:
        if not self.rows:
            return 0.0
        # A skipped file counts as wrong: the user still ends up with an unsorted screenshot.
        correct = sum(1 for r in self.rows if r.got_category == r.expected_category)
        return correct / len(self.rows)

    @property
    def sensitive_missed(self) -> list[str]:
        """Sensitive screenshots the model did not flag. The gate that must be zero."""
        return [r.file for r in self.rows if r.expected_sensitive and r.got_sensitive is not True]

    @property
    def sensitive_false_alarms(self) -> list[str]:
        return [r.file for r in self.rows if not r.expected_sensitive and r.got_sensitive is True]

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.rows if r.error is not None)

    @property
    def retries(self) -> int:
        return sum(1 for r in self.usable if r.retried)


def load_set(which: str) -> tuple[Path, list[dict]]:
    if which == "synthetic":
        base = ROOT / "samples" / "synthetic"
        labels = json.loads((base / "expected-labels.json").read_text("utf-8"))
        return base / "images", [f for f in labels["files"]]
    base = ROOT / "samples"
    labels = json.loads((base / "expected-labels.json").read_text("utf-8"))
    # The real set holds a video and product photos; only screenshots carry a category.
    return base, [f for f in labels["files"] if f["kind"] == "screenshot"]


def run_one(model: str, size: int, images_dir: Path, entries: list[dict]) -> RunResult:
    vision = OllamaVision(OLLAMA_URL, lambda: model, prompts_dir=ROOT / "api" / "prompts")
    result = RunResult(model=model, size=size)

    # Each run starts from an empty engine, so the peak belongs to this model alone.
    unload_all()

    with OllamaMemory() as memory:
        for index, entry in enumerate(entries, 1):
            path = images_dir / entry["file"]
            print(f"  [{index:>2}/{len(entries)}] {entry['file'][:46]:<46}", end="", flush=True)
            try:
                loaded = load_for_analysis(path, max_px=size)
            except ApiError as exc:
                print(f" unreadable ({exc.code})")
                continue

            started = time.monotonic()
            try:
                vr = vision.analyze(loaded.image)
            except ApiError as exc:
                wall = time.monotonic() - started
                result.rows.append(
                    Row(
                        entry["file"],
                        entry["category"],
                        None,
                        bool(entry["sensitive"]),
                        None,
                        None,
                        wall,
                        False,
                        exc.code,
                    )
                )
                print(f" {wall:6.2f}s  SKIPPED ({exc.code})")
                continue

            analysis = vr.analysis
            ok = analysis.category.value == entry["category"]
            result.rows.append(
                Row(
                    entry["file"],
                    entry["category"],
                    analysis.category.value,
                    bool(entry["sensitive"]),
                    analysis.sensitive,
                    analysis.slug,
                    vr.seconds,
                    vr.retried,
                )
            )
            mark = "ok " if ok else "MISS"
            print(f" {vr.seconds:6.2f}s  {mark} {analysis.category.value:<18} {analysis.slug[:34]}")

    result.peak_bytes = memory.peak_bytes
    result.baseline_bytes = memory.baseline_bytes
    return result


def verdict(r: RunResult) -> tuple[bool, list[str]]:
    failures = []
    if r.seconds_median > TARGET_SECONDS:
        failures.append(f"{r.seconds_median:.1f}s median > {TARGET_SECONDS:.0f}s")
    gb = r.peak_bytes / 1024**3
    if gb > TARGET_PEAK_GB:
        failures.append(f"{gb:.2f} GB peak > {TARGET_PEAK_GB:.0f} GB")
    if r.category_accuracy < TARGET_CATEGORY_ACCURACY:
        failures.append(f"{r.category_accuracy:.0%} accuracy < {TARGET_CATEGORY_ACCURACY:.0%}")
    if r.sensitive_missed:
        failures.append(f"{len(r.sensitive_missed)} sensitive missed")
    return not failures, failures


def table(results: list[RunResult]) -> str:
    header = (
        "| Model | px | s/shot (median) | s/shot (mean) | Peak RAM | Category | "
        "Sensitive missed | False alarms | Skipped | Retries | Meets targets |"
    )
    rule = "| " + " | ".join(["---"] * 11) + " |"
    out = [header, rule]
    for r in results:
        ok, failures = verdict(r)
        out.append(
            f"| `{r.model}` | {r.size} | {r.seconds_median:.2f} | {r.seconds_mean:.2f} | "
            f"{r.peak_bytes / 1024**3:.2f} GB | {r.category_accuracy:.0%} "
            f"({sum(1 for x in r.rows if x.got_category == x.expected_category)}/{len(r.rows)}) | "
            f"{len(r.sensitive_missed)} | {len(r.sensitive_false_alarms)} | {r.skipped} | "
            f"{r.retries} | {'**yes**' if ok else 'no — ' + '; '.join(failures)} |"
        )
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    parser.add_argument("--set", dest="which", choices=["synthetic", "real"], default="synthetic")
    parser.add_argument(
        "--limit", type=int, default=0, help="only the first N images (a smoke run)"
    )
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    images_dir, entries = load_set(args.which)
    if args.limit:
        entries = entries[: args.limit]

    print(f"set={args.which}  images={len(entries)}  models={models}  sizes={sizes}")
    print(f"prompt={PROMPT_VERSION}  host={platform.platform()}\n")

    results: list[RunResult] = []
    for model in models:
        for size in sizes:
            print(f"--- {model} @ {size}px ---")
            results.append(run_one(model, size, images_dir, entries))
            print()

    print(table(results))

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = HERE / "results" / f"{socket.gethostname().split('.')[0]}-{args.which}-{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "generated": stamp,
                "set": args.which,
                "prompt_version": PROMPT_VERSION,
                "host": {
                    "platform": platform.platform(),
                    "machine": platform.machine(),
                    "python": platform.python_version(),
                    "cpu_count": psutil.cpu_count(),
                    "total_ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
                },
                "targets": {
                    "seconds": TARGET_SECONDS,
                    "peak_gb": TARGET_PEAK_GB,
                    "category_accuracy": TARGET_CATEGORY_ACCURACY,
                },
                "runs": [
                    {
                        **{k: v for k, v in asdict(r).items() if k != "rows"},
                        "seconds_median": r.seconds_median,
                        "seconds_mean": r.seconds_mean,
                        "category_accuracy": r.category_accuracy,
                        "sensitive_missed": r.sensitive_missed,
                        "sensitive_false_alarms": r.sensitive_false_alarms,
                        "skipped": r.skipped,
                        "retries": r.retries,
                        "meets_targets": verdict(r)[0],
                        "failures": verdict(r)[1],
                        "rows": [asdict(x) for x in r.rows],
                    }
                    for r in results
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
