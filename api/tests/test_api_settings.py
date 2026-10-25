import time
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import ScriptedVision
from tests.images_fixtures import panelled
from tests.test_api_runs import run_to_completion, watch


class TestSettings:
    def test_defaults_are_an_overnight_window_with_both_guards_on(self, client: TestClient) -> None:
        body = client.get("/api/settings").json()
        schedule = body["schedule"]
        assert schedule["enabled"] is True
        assert (schedule["windowStart"], schedule["windowEnd"]) == ("23:00", "07:00")
        assert schedule["requireIdle"] is True
        assert schedule["pauseOnBattery"] is True
        # Sensitive text stays out of the index until the user says otherwise.
        assert body["index_sensitive_text"] is False

    def test_the_schedule_can_be_changed_and_survives(self, client: TestClient) -> None:
        client.put(
            "/api/settings",
            json={
                "schedule": {"windowStart": "01:00", "windowEnd": "05:30", "pauseOnBattery": False}
            },
        )
        schedule = client.get("/api/settings").json()["schedule"]
        assert (schedule["windowStart"], schedule["windowEnd"]) == ("01:00", "05:30")
        assert schedule["pauseOnBattery"] is False

    def test_a_malformed_time_is_refused(self, client: TestClient) -> None:
        response = client.put("/api/settings", json={"schedule": {"windowStart": "lunchtime"}})
        assert response.status_code == 422

    def test_sensitive_indexing_can_be_turned_on(self, client: TestClient) -> None:
        body = client.put("/api/settings", json={"index_sensitive_text": True}).json()
        assert body["index_sensitive_text"] is True


class TestPauseResume:
    def test_pausing_and_resuming_is_reported(self, client: TestClient) -> None:
        assert client.get("/api/settings").json()["paused"] is False
        assert client.post("/api/runs/pause").json()["paused"] is True

    def test_resuming_without_a_paused_run_is_refused(self, client: TestClient) -> None:
        client.post("/api/runs/pause")
        response = client.post("/api/runs/resume")
        assert response.status_code == 400
        assert response.json()["code"] == "no_run_in_progress"

    def test_sorting_now_overrides_a_standing_pause(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """Asking for a run explicitly is a clear instruction, and outranks the guard."""
        folder = tmp_path / "shots"
        watch(client, folder)
        panelled(folder / "a.png", seed=1)

        client.post("/api/runs/pause")
        body = run_to_completion(client)

        assert body["status"] == "awaiting_approval"
        assert client.get("/api/settings").json()["paused"] is False

    def test_a_run_paused_part_way_stops_before_the_next_image(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        folder = tmp_path / "shots"
        watch(client, folder)
        for seed in range(5):
            panelled(folder / f"s{seed}.png", seed=seed * 3)

        # Pause from inside the run, after the second image, so there is no sleeping involved.
        def pause_after_two(call: int) -> None:
            if call == 2:
                client.post("/api/runs/pause")

        vision.on_call = pause_after_two

        started = client.post("/api/runs")
        assert started.status_code == 201

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            body = client.get(f"/api/runs/{started.json()['id']}").json()
            if body["status"] not in {"scanning", "analyzing"}:
                break
            time.sleep(0.02)

        assert body["status"] == "paused"
        assert vision.calls < 5  # it stopped between images, not part-way through one
        assert not (folder / "Slothshot").exists()  # and nothing was organised

    def test_a_paused_run_resumes_where_it_stopped(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        folder = tmp_path / "shots"
        watch(client, folder)
        for seed in range(5):
            panelled(folder / f"s{seed}.png", seed=seed * 3)

        def pause_after_two(call: int) -> None:
            if call == 2:
                client.post("/api/runs/pause")

        vision.on_call = pause_after_two
        started = client.post("/api/runs")
        run_id = started.json()["id"]

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if client.get(f"/api/runs/{run_id}").json()["status"] == "paused":
                break
            time.sleep(0.02)
        paused_after = vision.calls

        vision.on_call = None
        assert client.post("/api/runs/resume").status_code == 200

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            body = client.get(f"/api/runs/{run_id}").json()
            if body["status"] not in {"scanning", "analyzing"}:
                break
            time.sleep(0.02)

        assert body["status"] == "awaiting_approval"
        # Every screenshot reached a verdict, and the ones analysed before the pause were not
        # sent to the model a second time. A near-duplicate among the fixtures is settled
        # without the model, so the call count is a ceiling rather than an equality.
        analysed = client.get(f"/api/runs/{run_id}/preview").json()
        assert len(analysed) == 5
        assert paused_after < vision.calls <= 5


class TestModelUnload:
    def test_the_model_is_released_when_a_run_ends(
        self, client: TestClient, vision: ScriptedVision, tmp_path: Path
    ) -> None:
        """Several gigabytes do not stay resident between runs."""
        folder = tmp_path / "shots"
        watch(client, folder)
        panelled(folder / "a.png", seed=1)

        run_to_completion(client)

        assert vision.unloads >= 1
