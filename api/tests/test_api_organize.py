from pathlib import Path

from fastapi.testclient import TestClient

from tests.images_fixtures import panelled
from tests.test_api_runs import run_to_completion, watch

ORGANIZED = "Slothshot"


def files_under(folder: Path) -> set[Path]:
    return {p.relative_to(folder) for p in folder.rglob("*") if p.is_file()}


def test_the_first_run_waits_for_approval_before_moving_anything(
    client: TestClient, tmp_path: Path
) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    before = files_under(folder)

    run = run_to_completion(client)

    assert run["status"] == "awaiting_approval"
    assert files_under(folder) == before  # nothing has moved yet

    plan = client.get(f"/api/runs/{run['id']}/plan").json()
    assert len(plan) == 1
    assert plan[0]["to_path"].endswith(".png")
    assert ORGANIZED in plan[0]["to_path"]
    assert files_under(folder) == before  # asking for the plan still changes nothing


def test_approving_carries_out_the_run(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)

    run = run_to_completion(client)
    approved = client.post(f"/api/runs/{run['id']}/approve")

    assert approved.status_code == 200
    assert approved.json()["status"] == "done"
    assert not (folder / "a.png").exists()
    assert len(files_under(folder)) == 1  # moved, not copied, and nothing lost


def test_later_runs_do_not_ask_again(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    first = run_to_completion(client)
    client.post(f"/api/runs/{first['id']}/approve")

    panelled(folder / "b.png", seed=9)
    second = run_to_completion(client)

    assert second["status"] == "done"
    assert not (folder / "b.png").exists()


def test_approving_twice_is_refused(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    run = run_to_completion(client)
    client.post(f"/api/runs/{run['id']}/approve")

    again = client.post(f"/api/runs/{run['id']}/approve")
    assert again.status_code == 409
    assert again.json()["code"] == "already_approved"


def test_undoing_a_run_over_the_api(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    before = files_under(folder)

    run = run_to_completion(client)
    client.post(f"/api/runs/{run['id']}/approve")
    assert files_under(folder) != before

    undone = client.post(f"/api/runs/{run['id']}/undo")
    assert undone.status_code == 200
    assert undone.json()["restored"] == 1
    assert files_under(folder) == before


def test_undoing_one_screenshot_over_the_api(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    panelled(folder / "b.png", seed=9)

    run = run_to_completion(client)
    client.post(f"/api/runs/{run['id']}/approve")
    preview = client.get(f"/api/runs/{run['id']}/preview").json()

    undone = client.post(f"/api/screenshots/{preview[0]['id']}/undo")
    assert undone.json()["restored"] == 1
    # Exactly one came back; the other is still filed.
    assert len([p for p in folder.iterdir() if p.is_file()]) == 1


def test_undoing_everything_over_the_api(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    watch(client, folder)
    panelled(folder / "a.png", seed=1)
    before = files_under(folder)
    run = run_to_completion(client)
    client.post(f"/api/runs/{run['id']}/approve")

    undone = client.post("/api/undo/everything")
    assert undone.json()["restored"] == 1
    assert files_under(folder) == before


def test_undoing_an_unknown_screenshot_is_refused(client: TestClient) -> None:
    assert client.post("/api/screenshots/999/undo").status_code == 404


def test_undoing_when_nothing_has_happened_is_refused(client: TestClient) -> None:
    response = client.post("/api/undo/everything")
    assert response.status_code == 400
    assert response.json()["code"] == "nothing_to_undo"
