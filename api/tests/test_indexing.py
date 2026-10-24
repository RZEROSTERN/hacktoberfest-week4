import os
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.db import make_engine
from app.errors import ApiError
from app.images import load_for_analysis
from app.indexing import DUPLICATE_DISTANCE, Indexer, iter_images
from app.models import Category, Run, Screenshot, ShotStatus
from app.schemas import Analysis
from app.settings_store import INDEX_SENSITIVE_TEXT, set_flag
from app.vision import VisionResult
from tests.images_fixtures import panelled


class FakeVision:
    """Returns a scripted answer and counts how often it was asked."""

    def __init__(self, *answers: Analysis | ApiError) -> None:
        self.answers = list(answers)
        self.calls = 0

    def analyze(self, image: Image.Image) -> VisionResult:
        self.calls += 1
        answer = self.answers[min(self.calls - 1, len(self.answers) - 1)]
        if isinstance(answer, ApiError):
            raise answer
        return VisionResult(
            analysis=answer, seconds=0.1, retried=False, model="fake:1", prompt_version="analyze.v1"
        )


def analysis(**over: object) -> Analysis:
    return Analysis.model_validate(
        {
            "slug": "a-screenshot",
            "category": "other",
            "description": "d",
            "text": "some text",
            "sensitive": False,
        }
        | over
    )


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    data = tmp_path / "data"
    data.mkdir()
    return make_engine(data)


@pytest.fixture
def run_id(engine: Engine) -> int:
    with Session(engine) as session:
        run = Run()
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id is not None
        return run.id


def shots(engine: Engine) -> list[Screenshot]:
    with Session(engine) as session:
        return list(session.exec(select(Screenshot)).all())


class TestIterImages:
    def test_finds_images_and_ignores_everything_else(self, tmp_path: Path) -> None:
        panelled(tmp_path / "a.png", seed=1)
        (tmp_path / "notes.txt").write_text("hello")
        (tmp_path / "clip.mp4").write_bytes(b"\x00\x01")
        found = {f.path.name for f in iter_images([tmp_path])}
        assert found == {"a.png"}

    def test_skips_slothshots_own_output(self, tmp_path: Path) -> None:
        panelled(tmp_path / "loose.png", seed=1)
        organized = tmp_path / "Slothshot" / "receipt"
        organized.mkdir(parents=True)
        panelled(organized / "already-sorted.png", seed=2)
        found = {f.path.name for f in iter_images([tmp_path])}
        # Re-reading our own output would sort already-sorted files a second time.
        assert found == {"loose.png"}

    def test_skips_empty_files(self, tmp_path: Path) -> None:
        (tmp_path / "empty.png").write_bytes(b"")
        assert list(iter_images([tmp_path])) == []

    def test_walks_subfolders_and_tolerates_a_missing_folder(self, tmp_path: Path) -> None:
        nested = tmp_path / "trip" / "2026"
        nested.mkdir(parents=True)
        panelled(nested / "deep.png", seed=3)
        found = {f.path.name for f in iter_images([tmp_path, tmp_path / "nope"])}
        assert found == {"deep.png"}


class TestScan:
    def test_records_each_new_file_once(self, engine: Engine, run_id: int, tmp_path: Path) -> None:
        panelled(tmp_path / "a.png", seed=1)
        panelled(tmp_path / "b.png", seed=2)
        indexer = Indexer(engine, FakeVision(analysis()), 768)
        assert indexer.scan(run_id, [tmp_path]) == 2
        assert len(shots(engine)) == 2

    def test_rescanning_adds_nothing_and_never_reanalyses(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        panelled(tmp_path / "a.png", seed=1)
        indexer = Indexer(engine, FakeVision(analysis()), 768)
        indexer.scan(run_id, [tmp_path])
        assert indexer.scan(run_id, [tmp_path]) == 0
        assert len(shots(engine)) == 1

    def test_a_file_the_user_renamed_is_recognised_by_its_bytes(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        original = panelled(tmp_path / "a.png", seed=1)
        indexer = Indexer(engine, FakeVision(analysis()), 768)
        indexer.scan(run_id, [tmp_path])

        renamed = tmp_path / "holiday.png"
        original.rename(renamed)
        assert indexer.scan(run_id, [tmp_path]) == 0  # not a new screenshot

        row = shots(engine)[0]
        assert row.current_path == str(renamed)
        assert row.original_path == str(original)  # undo still knows where it started


class TestAnalyze:
    def test_asks_the_model_once_per_unique_image(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        panelled(tmp_path / "a.png", seed=1)
        panelled(tmp_path / "b.png", seed=9)
        vision = FakeVision(analysis(slug="first"), analysis(slug="second"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        assert vision.calls == 2
        assert all(s.status is ShotStatus.ANALYZED for s in shots(engine))

    def test_an_exact_copy_is_settled_without_the_model(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        source = panelled(tmp_path / "a.png", seed=1)
        (tmp_path / "a-copy.png").write_bytes(source.read_bytes())

        vision = FakeVision(analysis(slug="the-one"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        # Identical bytes collapse at the content hash, before any image is even opened.
        assert vision.calls == 1
        assert len(shots(engine)) == 1

    def test_a_resized_copy_is_caught_by_the_perceptual_hash(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        source = panelled(tmp_path / "original.png", seed=4, size=(800, 600))
        with Image.open(source) as im:
            im.resize((im.width // 2, im.height // 2)).save(tmp_path / "copy.png")
        # The copy was made after the original, and that is what decides which one is kept.
        os.utime(source, (1_700_000_000, 1_700_000_000))
        os.utime(tmp_path / "copy.png", (1_700_009_999, 1_700_009_999))

        vision = FakeVision(analysis(slug="the-one", category="receipt"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        assert vision.calls == 1  # different bytes, same picture: the model is not asked twice
        rows = {Path(s.current_path).name: s for s in shots(engine)}
        assert rows["original.png"].duplicate_of_id is None  # the one taken first is kept
        assert rows["copy.png"].duplicate_of_id == rows["original.png"].id
        assert rows["copy.png"].category is Category.RECEIPT  # inherits the twin's labels

        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None
            assert run.duplicates == 1
            assert run.reviewable_bytes > 0

    def test_two_similar_but_different_screenshots_are_kept_apart(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        """The real set's hardest case: same layout, different content, five seconds apart."""
        panelled(tmp_path / "a.png", seed=1)
        panelled(tmp_path / "b.png", seed=9)
        vision = FakeVision(analysis(slug="one"), analysis(slug="two"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        assert vision.calls == 2
        assert all(s.duplicate_of_id is None for s in shots(engine))

    def test_the_threshold_sits_below_the_closest_measured_false_pair(self) -> None:
        # Genuine duplicates measured 0; the nearest non-duplicate measured 7 in the fixtures
        # and 8 in the real captures. See docs/DECISIONS.md.
        assert 0 < DUPLICATE_DISTANCE < 7

    def test_an_unreadable_image_is_skipped_and_the_run_continues(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        (tmp_path / "broken.png").write_bytes(b"not a png at all")
        panelled(tmp_path / "fine.png", seed=2)
        vision = FakeVision(analysis())
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        by_name = {Path(s.current_path).name: s for s in shots(engine)}
        assert by_name["broken.png"].status is ShotStatus.SKIPPED
        assert by_name["fine.png"].status is ShotStatus.ANALYZED

    def test_a_model_that_cannot_be_understood_skips_that_file_only(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        panelled(tmp_path / "a.png", seed=1)
        panelled(tmp_path / "b.png", seed=9)
        vision = FakeVision(ApiError(422, "invalid_model_output"), analysis(slug="second"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        statuses = sorted(s.status.value for s in shots(engine))
        assert statuses == ["analyzed", "skipped"]
        with Session(engine) as session:
            run = session.get(Run, run_id)
            assert run is not None and run.skipped == 1

    def test_a_file_that_vanished_is_marked_missing_not_skipped(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        path = panelled(tmp_path / "a.png", seed=1)
        indexer = Indexer(engine, FakeVision(analysis()), 768)
        indexer.scan(run_id, [tmp_path])
        path.unlink()
        indexer.analyze_pending(run_id)
        assert shots(engine)[0].status is ShotStatus.MISSING


class TestSensitiveText:
    def test_sensitive_text_is_not_stored_by_default(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        panelled(tmp_path / "a.png", seed=1)
        vision = FakeVision(analysis(sensitive=True, text="card 4111 1111 1111 1111"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)

        row = shots(engine)[0]
        assert row.sensitive is True
        assert row.extracted_text is None  # sorted, but never indexed

    def test_sensitive_text_is_stored_when_the_user_turns_it_on(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        set_flag(engine, INDEX_SENSITIVE_TEXT, True)
        panelled(tmp_path / "a.png", seed=1)
        vision = FakeVision(analysis(sensitive=True, text="secret"))
        indexer = Indexer(engine, vision, 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)
        assert shots(engine)[0].extracted_text == "secret"

    def test_ordinary_text_is_always_stored(
        self, engine: Engine, run_id: int, tmp_path: Path
    ) -> None:
        panelled(tmp_path / "a.png", seed=1)
        indexer = Indexer(engine, FakeVision(analysis(text="a booking number")), 768)
        indexer.scan(run_id, [tmp_path])
        indexer.analyze_pending(run_id)
        assert shots(engine)[0].extracted_text == "a booking number"


class TestDownscaling:
    def test_the_model_only_ever_sees_the_downscaled_image(self, tmp_path: Path) -> None:
        path = panelled(tmp_path / "big.png", seed=4, size=(3456, 2234))
        loaded = load_for_analysis(path, 768)
        assert max(loaded.image.size) == 768
        assert (loaded.width, loaded.height) == (3456, 2234)
