"""Organizing and undoing. The guarantee under test: nothing is deleted, and every change
can be put back exactly as it was."""

import os
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.db import make_engine
from app.errors import ApiError
from app.indexing import Indexer
from app.models import Change, Run, Screenshot
from app.naming import REVIEW_DIR_NAME
from app.organize import Organizer
from app.schemas import Analysis
from app.undo import undo_everything, undo_file, undo_run
from tests.images_fixtures import panelled
from tests.test_indexing import FakeVision, analysis

ORGANIZED = "Slothshot"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    data = tmp_path / "data"
    data.mkdir()
    return make_engine(data)


@pytest.fixture
def shots_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "shots"
    folder.mkdir()
    return folder


def new_run(engine: Engine) -> int:
    with Session(engine) as session:
        run = Run()
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.id is not None
        return run.id


def index(engine: Engine, folder: Path, *answers: Analysis) -> int:
    """Scan and analyse, returning the run id."""
    run_id = new_run(engine)
    indexer = Indexer(engine, FakeVision(*(answers or (analysis(),))), 768)
    indexer.scan(run_id, [folder])
    indexer.analyze_pending(run_id)
    return run_id


def files_under(folder: Path) -> set[Path]:
    return {p.relative_to(folder) for p in folder.rglob("*") if p.is_file()}


def count_files(folder: Path) -> int:
    return len(files_under(folder))


class TestOrganize:
    def test_files_land_in_their_category_folder(self, engine: Engine, shots_dir: Path) -> None:
        path = panelled(shots_dir / "a.png", seed=1)
        os.utime(path, (1_757_000_000, 1_757_000_000))  # 2025-09-04
        run_id = index(engine, shots_dir, analysis(slug="a-receipt", category="receipt"))

        moved = Organizer(engine).organize(run_id, [shots_dir])

        assert moved == 1
        assert not path.exists()
        landed = list((shots_dir / ORGANIZED / "receipt").iterdir())
        assert len(landed) == 1
        assert landed[0].name.endswith("-a-receipt.png")
        assert landed[0].name[:4].isdigit()  # dated prefix

    def test_a_duplicate_goes_to_review(self, engine: Engine, shots_dir: Path) -> None:
        source = panelled(shots_dir / "original.png", seed=4, size=(800, 600))
        from PIL import Image

        with Image.open(source) as im:
            im.resize((im.width // 2, im.height // 2)).save(shots_dir / "copy.png")
        os.utime(source, (1_700_000_000, 1_700_000_000))
        os.utime(shots_dir / "copy.png", (1_700_009_999, 1_700_009_999))

        run_id = index(engine, shots_dir, analysis(slug="a-shot", category="receipt"))
        Organizer(engine).organize(run_id, [shots_dir])

        assert count_files(shots_dir / ORGANIZED / REVIEW_DIR_NAME) == 1
        assert count_files(shots_dir / ORGANIZED / "receipt") == 1

    def test_an_expired_item_goes_to_review(self, engine: Engine, shots_dir: Path) -> None:
        panelled(shots_dir / "pass.png", seed=1)
        run_id = index(
            engine,
            shots_dir,
            analysis(
                slug="boarding-pass",
                category="ticket or booking",
                expiry_hint="flight departed 4 February 2020",
            ),
        )
        Organizer(engine).organize(run_id, [shots_dir])
        assert count_files(shots_dir / ORGANIZED / REVIEW_DIR_NAME) == 1

    def test_nothing_is_ever_deleted(self, engine: Engine, shots_dir: Path) -> None:
        for index_ in range(5):
            panelled(shots_dir / f"s{index_}.png", seed=index_)
        before = count_files(shots_dir)

        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])

        assert count_files(shots_dir) == before == 5

    def test_a_name_collision_keeps_both_files(self, engine: Engine, shots_dir: Path) -> None:
        """Two different screenshots from the same day can earn the same description."""
        first = panelled(shots_dir / "one.png", seed=1)
        second = panelled(shots_dir / "two.png", seed=9)
        for path in (first, second):
            os.utime(path, (1_757_000_000, 1_757_000_000))  # same capture date

        run_id = index(
            engine,
            shots_dir,
            analysis(slug="same-name", category="other"),
            analysis(slug="same-name", category="other"),
        )
        Organizer(engine).organize(run_id, [shots_dir])

        landed = {p.name for p in (shots_dir / ORGANIZED / "other").iterdir()}
        assert len(landed) == 2  # neither file was overwritten
        assert any(n.endswith("-same-name.png") for n in landed)
        assert any(n.endswith("-same-name-2.png") for n in landed)

    def test_an_already_organized_file_is_left_where_it_is(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        organizer = Organizer(engine)
        organizer.organize(run_id, [shots_dir])
        placed = files_under(shots_dir)

        second = index(engine, shots_dir, analysis(slug="a-shot"))
        assert organizer.organize(second, [shots_dir]) == 0
        assert files_under(shots_dir) == placed

    def test_the_plan_touches_nothing(self, engine: Engine, shots_dir: Path) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        before = files_under(shots_dir)

        planned = Organizer(engine).plan(run_id, [shots_dir])

        assert len(planned) == 1
        assert files_under(shots_dir) == before


class TestJournal:
    def test_every_move_is_recorded_and_marked_applied(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])

        with Session(engine) as session:
            moves = [c for c in session.exec(select(Change)).all() if c.kind.value == "move"]
            assert len(moves) == 1
            assert moves[0].applied is True
            assert moves[0].applied_at is not None
            assert Path(moves[0].to_path).exists()
            assert not Path(moves[0].from_path or "").exists()


class TestUndo:
    def test_a_single_file_goes_back_to_its_exact_original_path(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        original = panelled(shots_dir / "holiday snap.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])
        assert not original.exists()

        with Session(engine) as session:
            shot_id = session.exec(select(Screenshot)).first().id  # type: ignore[union-attr]
        assert shot_id is not None

        assert undo_file(engine, shot_id) == 1
        assert original.exists()  # same folder, same name, spaces and all

    def test_undoing_a_run_puts_everything_back(self, engine: Engine, shots_dir: Path) -> None:
        names = ["a.png", "b.png", "c.png"]
        for position, name in enumerate(names):
            panelled(shots_dir / name, seed=position)
        before = files_under(shots_dir)

        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])
        assert files_under(shots_dir) != before

        assert undo_run(engine, run_id) == 3
        assert files_under(shots_dir) == before

    def test_undoing_everything_puts_every_run_back(self, engine: Engine, shots_dir: Path) -> None:
        panelled(shots_dir / "a.png", seed=1)
        before = files_under(shots_dir)
        organizer = Organizer(engine)
        organizer.organize(index(engine, shots_dir, analysis(slug="first")), [shots_dir])

        panelled(shots_dir / "b.png", seed=9)
        before_both = before | {Path("b.png")}
        organizer.organize(index(engine, shots_dir, analysis(slug="second")), [shots_dir])

        assert undo_everything(engine) == 2
        assert files_under(shots_dir) == before_both

    def test_undo_after_a_collision_restores_both_original_names(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        """The file that was renamed to `-2` must still find its way home."""
        for name in ("one.png", "two.png"):
            path = panelled(shots_dir / name, seed=1 if name == "one.png" else 9)
            os.utime(path, (1_757_000_000, 1_757_000_000))
        before = files_under(shots_dir)

        run_id = index(
            engine,
            shots_dir,
            analysis(slug="same-name"),
            analysis(slug="same-name"),
        )
        Organizer(engine).organize(run_id, [shots_dir])
        assert len(list((shots_dir / ORGANIZED / "other").iterdir())) == 2

        assert undo_run(engine, run_id) == 2
        assert files_under(shots_dir) == before

    def test_undo_removes_the_folders_it_created(self, engine: Engine, shots_dir: Path) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot", category="receipt"))
        Organizer(engine).organize(run_id, [shots_dir])
        assert (shots_dir / ORGANIZED / "receipt").is_dir()

        undo_run(engine, run_id)
        assert not (shots_dir / ORGANIZED).exists()  # tidied away, because it was empty

    def test_a_folder_the_user_put_something_in_is_kept(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot", category="receipt"))
        Organizer(engine).organize(run_id, [shots_dir])
        (shots_dir / ORGANIZED / "receipt" / "notes.txt").write_text("mine")

        undo_run(engine, run_id)

        assert (shots_dir / ORGANIZED / "receipt" / "notes.txt").read_text() == "mine"

    def test_undoing_twice_is_refused_rather_than_repeated(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])
        undo_run(engine, run_id)

        with pytest.raises(ApiError) as caught:
            undo_run(engine, run_id)
        assert caught.value.code == "nothing_to_undo"


class TestUndoIsAllOrNothing:
    def test_a_file_moved_away_by_someone_else_blocks_the_whole_undo(
        self, engine: Engine, shots_dir: Path, tmp_path: Path
    ) -> None:
        for name in ("a.png", "b.png"):
            panelled(shots_dir / name, seed=1 if name == "a.png" else 9)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])

        organized = sorted((shots_dir / ORGANIZED / "other").iterdir())
        elsewhere = tmp_path / "taken-away.png"
        organized[0].rename(elsewhere)
        state = files_under(shots_dir)

        with pytest.raises(ApiError) as caught:
            undo_run(engine, run_id)
        assert caught.value.code == "undo_blocked_missing"
        # The promise the message makes: nothing was changed.
        assert files_under(shots_dir) == state

    def test_an_occupied_original_path_blocks_the_whole_undo(
        self, engine: Engine, shots_dir: Path
    ) -> None:
        for name in ("a.png", "b.png"):
            panelled(shots_dir / name, seed=1 if name == "a.png" else 9)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])

        # The user made a new file with the name one of the originals had.
        (shots_dir / "a.png").write_text("something new and not a screenshot")
        state = files_under(shots_dir)

        with pytest.raises(ApiError) as caught:
            undo_run(engine, run_id)
        assert caught.value.code == "undo_blocked_occupied"
        assert files_under(shots_dir) == state
        assert (shots_dir / "a.png").read_text() == "something new and not a screenshot"

    def test_a_blocked_undo_leaves_the_journal_untouched(
        self, engine: Engine, shots_dir: Path, tmp_path: Path
    ) -> None:
        panelled(shots_dir / "a.png", seed=1)
        run_id = index(engine, shots_dir, analysis(slug="a-shot"))
        Organizer(engine).organize(run_id, [shots_dir])
        organized = next((shots_dir / ORGANIZED / "other").iterdir())
        organized.rename(tmp_path / "gone.png")

        with pytest.raises(ApiError):
            undo_run(engine, run_id)

        with Session(engine) as session:
            moves = [c for c in session.exec(select(Change)).all() if c.kind.value == "move"]
            assert all(c.undone_at is None for c in moves)  # still undoable once put back
