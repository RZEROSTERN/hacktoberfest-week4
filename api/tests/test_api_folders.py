from pathlib import Path

from fastapi.testclient import TestClient

from tests.images_fixtures import panelled


def test_starts_with_no_watched_folders(client: TestClient) -> None:
    assert client.get("/api/folders").json() == []


def test_adds_a_folder(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    folder.mkdir()
    response = client.post("/api/folders", json={"path": str(folder)})
    assert response.status_code == 201
    assert response.json()["path"] == str(folder.resolve())
    assert len(client.get("/api/folders").json()) == 1


def test_refuses_a_folder_that_is_not_there(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/folders", json={"path": str(tmp_path / "nope")})
    assert response.status_code == 400
    assert response.json()["code"] == "folder_not_found"


def test_refuses_a_file(client: TestClient, tmp_path: Path) -> None:
    target = panelled(tmp_path / "a.png", seed=1)
    response = client.post("/api/folders", json={"path": str(target)})
    assert response.status_code == 400
    assert response.json()["code"] == "not_a_folder"


def test_refuses_the_same_folder_twice(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    folder.mkdir()
    client.post("/api/folders", json={"path": str(folder)})
    response = client.post("/api/folders", json={"path": str(folder)})
    assert response.status_code == 409
    assert response.json()["code"] == "folder_already_watched"


def test_refuses_a_folder_already_covered_by_a_watched_one(
    client: TestClient, tmp_path: Path
) -> None:
    parent = tmp_path / "pictures"
    child = parent / "2026"
    child.mkdir(parents=True)
    client.post("/api/folders", json={"path": str(parent)})
    response = client.post("/api/folders", json={"path": str(child)})
    assert response.status_code == 409
    assert response.json()["code"] == "folder_inside_watched"


def test_refuses_slothshots_own_output_folder(client: TestClient, tmp_path: Path) -> None:
    organized = tmp_path / "Slothshot" / "receipt"
    organized.mkdir(parents=True)
    response = client.post("/api/folders", json={"path": str(organized)})
    assert response.status_code == 400
    assert response.json()["code"] == "cannot_watch_organized"


def test_removes_a_folder(client: TestClient, tmp_path: Path) -> None:
    folder = tmp_path / "shots"
    folder.mkdir()
    folder_id = client.post("/api/folders", json={"path": str(folder)}).json()["id"]
    assert client.delete(f"/api/folders/{folder_id}").status_code == 204
    assert client.get("/api/folders").json() == []


def test_removing_a_folder_that_is_not_there_is_refused(client: TestClient) -> None:
    assert client.delete("/api/folders/999").status_code == 404
