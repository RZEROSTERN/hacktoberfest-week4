from datetime import date

import pytest

from app.expiry import find_date, is_expired

TODAY = date(2026, 10, 24)


class TestFindDate:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("flight departs 2026-02-04", date(2026, 2, 4)),
            ("flight departs 4 Feb 2026", date(2026, 2, 4)),
            ("flight departs 4 February 2026", date(2026, 2, 4)),
            ("event on February 4, 2026", date(2026, 2, 4)),
            ("event on Feb 4 2026", date(2026, 2, 4)),
        ],
    )
    def test_reads_a_fully_specified_date(self, text: str, expected: date) -> None:
        assert find_date(text) == expected

    @pytest.mark.parametrize(
        "text",
        ["delivery on 2 dic", "returns until 2 Jan", "one-time code, minutes", "", "no date here"],
    )
    def test_refuses_anything_without_a_year(self, text: str) -> None:
        # Guessing the year is how last month's boarding pass becomes next year's.
        assert find_date(text) is None

    def test_refuses_a_date_that_does_not_exist(self) -> None:
        assert find_date("30 February 2026") is None
        assert find_date("2026-13-01") is None


class TestIsExpired:
    def test_a_past_date_is_expired(self) -> None:
        assert is_expired("flight departs 4 Feb 2026", TODAY) is True

    def test_a_future_date_is_not(self) -> None:
        assert is_expired("doors open 12 December 2026", TODAY) is False

    def test_today_is_not_yet_expired(self) -> None:
        assert is_expired("valid until 2026-10-24", TODAY) is False

    @pytest.mark.parametrize("hint", [None, "", "one-time code, minutes", "delivery 2 dic"])
    def test_anything_it_cannot_resolve_is_left_alone(self, hint: str | None) -> None:
        # The cautious default: a screenshot filed normally costs nothing, while one wrongly
        # swept into Review costs the user a search.
        assert is_expired(hint, TODAY) is False
