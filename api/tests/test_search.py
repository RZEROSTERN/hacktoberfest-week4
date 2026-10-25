from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.schemas import Analysis
from tests.conftest import ScriptedVision
from tests.images_fixtures import panelled
from tests.test_api_runs import run_to_completion, watch


def index_one(client: TestClient, vision: ScriptedVision, folder: Path, answer: Analysis) -> None:
    vision.answer = answer
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    run_to_completion(client)


def answer(**over: object) -> Analysis:
    return Analysis.model_validate(
        {
            "slug": "a-screenshot",
            "category": "other",
            "description": "A plain screenshot.",
            "text": "",
            "sensitive": False,
        }
        | over
    )


def hits(client: TestClient, query: str) -> list[dict[str, Any]]:
    body = client.get("/api/search", params={"q": query}).json()
    return list(body["hits"])


class TestFinding:
    def test_finds_by_description(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        index_one(
            client, vision, tmp_path / "s", answer(description="A hotel booking confirmation.")
        )
        assert len(hits(client, "hotel")) == 1

    def test_finds_by_the_stored_text(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        index_one(client, vision, tmp_path / "s", answer(text="Booking reference QX7412"))
        found = hits(client, "qx7412")
        assert len(found) == 1
        assert "QX7412" in (found[0]["snippet"] or "")

    def test_finds_by_slug(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        index_one(client, vision, tmp_path / "s", answer(slug="northgate-market-receipt"))
        assert len(hits(client, "northgate")) == 1

    def test_every_word_must_match(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        index_one(
            client, vision, tmp_path / "s", answer(description="A hotel booking confirmation.")
        )
        assert len(hits(client, "hotel booking")) == 1
        assert len(hits(client, "hotel flight")) == 0

    def test_matching_ignores_case(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        index_one(client, vision, tmp_path / "s", answer(description="A Hotel Booking."))
        assert len(hits(client, "HOTEL")) == 1

    def test_an_empty_query_returns_nothing_rather_than_everything(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        index_one(client, vision, tmp_path / "s", answer(description="Anything at all."))
        assert hits(client, "") == []
        assert hits(client, "   ") == []


class TestSensitiveStaysOutOfTheIndex:
    def test_the_text_of_a_sensitive_screenshot_cannot_be_searched(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        """The secret was never stored, so there is nothing here to match against."""
        index_one(
            client,
            vision,
            tmp_path / "s",
            answer(
                sensitive=True,
                text="verification code 482913",
                description="A message with a one-time code.",
            ),
        )
        assert hits(client, "482913") == []

    def test_but_it_is_still_findable_by_its_description(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        # Being unable to find a screenshot at all would be its own kind of failure.
        index_one(
            client,
            vision,
            tmp_path / "s",
            answer(
                sensitive=True,
                text="verification code 482913",
                description="A message with a one-time code.",
            ),
        )
        found = hits(client, "one-time")
        assert len(found) == 1
        assert found[0]["sensitive"] is True
        assert found[0]["snippet"] is None  # nothing to quote

    def test_the_user_can_turn_indexing_on(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        from app.settings_store import INDEX_SENSITIVE_TEXT, set_flag

        engine = client.app.state.engine  # type: ignore[attr-defined]
        set_flag(engine, INDEX_SENSITIVE_TEXT, True)
        index_one(
            client,
            vision,
            tmp_path / "s",
            answer(sensitive=True, text="verification code 482913"),
        )
        assert len(hits(client, "482913")) == 1


class TestSummary:
    def test_an_empty_install_reports_zeroes_rather_than_failing(self, client: TestClient) -> None:
        body = client.get("/api/summary").json()
        assert body["run_id"] is None
        assert body["sorted_count"] == 0
        assert body["reclaimable_bytes"] == 0

    def test_counts_what_was_sorted_and_what_is_waiting(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        folder = tmp_path / "s"
        watch(client, folder)
        source = panelled(folder / "original.png", seed=4, size=(800, 600))
        (folder / "copy.png").write_bytes(source.read_bytes())  # an exact duplicate
        vision.answer = answer(slug="a-shot")

        run = run_to_completion(client)
        client.post(f"/api/runs/{run['id']}/approve")

        body = client.get("/api/summary").json()
        assert body["sorted_count"] == 2
        assert body["duplicates_waiting"] == 1
        assert body["reclaimable_bytes"] > 0  # what deleting the duplicate by hand would free
        assert body["total_indexed"] == 2
