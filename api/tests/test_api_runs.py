import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import ScriptedVision
from tests.images_fixtures import panelled

ACTIVE = {"scanning", "analyzing", "organizing"}


def watch(client: TestClient, folder: Path) -> None:
    folder.mkdir(exist_ok=True)
    assert client.post("/api/folders", json={"path": str(folder)}).status_code == 201


def run_to_completion(client: TestClient) -> dict[str, Any]:
    """Start a run and wait for the worker thread to finish it."""
    started = client.post("/api/runs")
    assert started.status_code == 201, started.json()
    run_id = started.json()["id"]

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get(f"/api/runs/{run_id}").json()
        if body["status"] not in ACTIVE:
            return body
        time.sleep(0.02)
    raise AssertionError(f"run {run_id} never finished")


def test_a_run_needs_a_folder_first(client: TestClient) -> None:
    response = client.post("/api/runs")
    assert response.status_code == 400
    assert response.json()["code"] == "folder_not_found"


def test_a_run_indexes_everything_it_finds(
    client: TestClient, vision: ScriptedVision, tmp_path: Path
) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    panelled(folder / "b.png", seed=9)

    body = run_to_completion(client)
    assert body["found"] == 2
    assert body["analyzed"] == 2
    assert vision.calls == 2

    preview = client.get(f"/api/runs/{body['id']}/preview").json()
    assert len(preview) == 2
    assert all(item["slug"] for item in preview)
    assert all(item["category"] for item in preview)


def test_the_preview_does_not_touch_any_file(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    original = panelled(folder / "a.png", seed=1)
    before = sorted(p.name for p in folder.iterdir())

    body = run_to_completion(client)
    client.get(f"/api/runs/{body['id']}/preview")

    assert sorted(p.name for p in folder.iterdir()) == before
    assert original.exists()  # nothing is renamed or moved until the user approves


def test_a_second_run_reuses_the_index_instead_of_the_model(
    client: TestClient, vision: ScriptedVision, tmp_path: Path
) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)

    run_to_completion(client)
    assert vision.calls == 1
    run_to_completion(client)
    assert vision.calls == 1  # the content hash already knows this file


def test_run_history_is_listed_newest_first(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    first = run_to_completion(client)["id"]
    second = run_to_completion(client)["id"]
    listed = [r["id"] for r in client.get("/api/runs").json()]
    assert listed[:2] == [second, first]


def test_an_unknown_run_is_refused(client: TestClient) -> None:
    assert client.get("/api/runs/999").status_code == 404
    assert client.get("/api/runs/999/preview").status_code == 404
