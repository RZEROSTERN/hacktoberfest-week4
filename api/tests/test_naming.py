from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from app.models import Category
from app.naming import MAX_STEM, destination_dir, stem_for, unique_path

WHEN = datetime(2026, 9, 7, 11, 7, tzinfo=UTC)


class TestStem:
    def test_puts_the_capture_date_first(self) -> None:
        assert stem_for(WHEN, "northgate-market-receipt") == "2026-09-07-northgate-market-receipt"

    def test_falls_back_to_the_slug_alone_without_a_date(self) -> None:
        assert stem_for(None, "a-receipt") == "a-receipt"

    def test_never_produces_an_empty_name(self) -> None:
        assert stem_for(None, "") == "screenshot"
        assert stem_for(None, "---") == "screenshot"

    def test_caps_the_length_without_leaving_a_trailing_dash(self) -> None:
        stem = stem_for(WHEN, "word-" * 60)
        assert len(stem) <= MAX_STEM
        assert not stem.endswith("-")

    def test_the_date_is_the_users_own_day_not_utc(self) -> None:
        """Stored times are UTC; a late evening in Mexico City is still the same day there."""
        cdmx = timezone(timedelta(hours=-6))
        evening = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)  # 19:30 on the 24th in CDMX
        assert evening.date().isoformat() == "2026-10-25"  # UTC has already rolled over
        assert stem_for(evening, "a-shot", tz=cdmx).startswith("2026-10-24")

    def test_the_same_instant_files_differently_in_different_zones(self) -> None:
        """Which is the point: the filename follows the user, not the clock in Greenwich."""
        instant = datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
        assert stem_for(instant, "a-shot", tz=UTC).startswith("2026-10-25")
        assert stem_for(instant, "a-shot", tz=timezone(timedelta(hours=-6))).startswith(
            "2026-10-24"
        )

    def test_a_dated_name_can_never_be_a_windows_device_name(self) -> None:
        # CON, PRN, AUX and friends are refused by Windows. A leading date makes them
        # unreachable, which is why the date goes first.
        assert stem_for(WHEN, "con").startswith("2026-")


class TestDestination:
    def test_files_by_category(self) -> None:
        got = destination_dir(Path("/shots"), "Slothshot", Category.RECEIPT, review=False)
        assert got == Path("/shots/Slothshot/receipt")

    def test_sends_review_items_to_one_place(self) -> None:
        got = destination_dir(Path("/shots"), "Slothshot", Category.RECEIPT, review=True)
        assert got == Path("/shots/Slothshot/Review")

    def test_an_unknown_category_lands_in_other(self) -> None:
        got = destination_dir(Path("/shots"), "Slothshot", None, review=False)
        assert got == Path("/shots/Slothshot/other")


class TestUniquePath:
    def test_uses_the_plain_name_when_nothing_is_there(self, tmp_path: Path) -> None:
        assert unique_path(tmp_path, "a-receipt", ".png") == tmp_path / "a-receipt.png"

    def test_counts_up_rather_than_overwriting(self, tmp_path: Path) -> None:
        (tmp_path / "a-receipt.png").write_bytes(b"first")
        assert unique_path(tmp_path, "a-receipt", ".png") == tmp_path / "a-receipt-2.png"

        (tmp_path / "a-receipt-2.png").write_bytes(b"second")
        assert unique_path(tmp_path, "a-receipt", ".png") == tmp_path / "a-receipt-3.png"

    def test_the_existing_file_is_left_alone(self, tmp_path: Path) -> None:
        existing = tmp_path / "a-receipt.png"
        existing.write_bytes(b"do not touch")
        unique_path(tmp_path, "a-receipt", ".png")
        assert existing.read_bytes() == b"do not touch"
