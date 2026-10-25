import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ollama import InstalledModel
from tests.conftest import ScriptedVision
from tests.test_setup import REAL, FakeCompat, FakeOllama


@pytest.fixture
def wizard(settings: Settings) -> Iterator[tuple[TestClient, FakeOllama, FakeCompat]]:
    ollama, compat = FakeOllama(), FakeCompat()
    app = create_app(settings, vision=ScriptedVision(), ollama=ollama, compat=compat)
    with TestClient(app) as client:
        yield client, ollama, compat


def settle(client: TestClient, timeout: float = 10) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get("/api/setup/progress").json()
        if body["state"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("setup never settled")


def test_a_fresh_install_is_not_ready_and_says_what_it_offers(
    wizard: tuple[TestClient, FakeOllama, FakeCompat],
) -> None:
    client, _, _ = wizard
    body = client.get("/api/setup/status").json()
    assert body["ready"] is False
    assert body["model"]["state"] == "not_selected"
    # Enough for the first screen: what to download, how big, how much RAM, which license.
    first = body["recommended"][0]
    assert {"model", "title", "size_bytes", "ram_gb", "license", "note"} <= set(first)


def test_nothing_downloads_until_it_is_asked_for(
    wizard: tuple[TestClient, FakeOllama, FakeCompat],
) -> None:
    client, ollama, _ = wizard
    client.get("/api/setup/status")
    client.get("/api/setup/progress")
    assert ollama.pulled == []


def test_downloading_a_model_makes_the_app_ready(
    wizard: tuple[TestClient, FakeOllama, FakeCompat],
) -> None:
    client, ollama, compat = wizard
    started = client.post("/api/setup/start", json={"model": REAL})
    assert started.status_code == 200

    assert settle(client)["state"] == "done"
    assert ollama.pulled == [REAL]
    assert compat.checked == [REAL]
    assert client.get("/api/setup/status").json()["ready"] is True


def test_a_model_that_cannot_read_an_image_is_refused(settings: Settings) -> None:
    app = create_app(
        settings,
        vision=ScriptedVision(),
        ollama=FakeOllama(),
        compat=FakeCompat(error="compat_no_vision"),
    )
    with TestClient(app) as client:
        client.post("/api/setup/start", json={"model": "some-text-model"})
        body = settle(client)
        assert body["state"] == "compat_failed"
        assert body["error_code"] == "compat_no_vision"
        assert client.get("/api/setup/status").json()["ready"] is False


def test_an_invalid_name_is_refused_before_anything_happens(
    wizard: tuple[TestClient, FakeOllama, FakeCompat],
) -> None:
    client, ollama, _ = wizard
    response = client.post("/api/setup/start", json={"model": "not a model name"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_model_name"
    assert ollama.pulled == []


def test_a_cloud_model_is_refused_by_name(
    wizard: tuple[TestClient, FakeOllama, FakeCompat],
) -> None:
    client, ollama, _ = wizard
    response = client.post("/api/setup/start", json={"model": "gemma4:cloud"})
    assert response.status_code == 400
    assert response.json()["code"] == "cloud_model"
    assert ollama.pulled == []


def test_a_second_download_while_one_runs_is_refused(settings: Settings) -> None:
    ollama = FakeOllama(pull_bytes=10_000_000, chunk_delay=0.05)
    app = create_app(settings, vision=ScriptedVision(), ollama=ollama, compat=FakeCompat())
    with TestClient(app) as client:
        client.post("/api/setup/start", json={"model": REAL})
        second = client.post("/api/setup/start", json={"model": "gemma4:e4b"})
        assert second.status_code == 409
        assert second.json()["code"] == "setup_busy"
        client.post("/api/setup/pause")
        settle(client)


def test_pausing_and_resuming_over_the_api(settings: Settings) -> None:
    ollama = FakeOllama(pull_bytes=10_000_000, chunk_delay=0.05)
    app = create_app(settings, vision=ScriptedVision(), ollama=ollama, compat=FakeCompat())
    with TestClient(app) as client:
        client.post("/api/setup/start", json={"model": REAL})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            step = next(
                s for s in client.get("/api/setup/progress").json()["steps"] if s["id"] == "model"
            )
            if step["completed"] > 0:
                break
            time.sleep(0.01)

        assert client.post("/api/setup/pause").status_code == 200
        assert settle(client)["state"] == "paused"
        assert client.post("/api/setup/resume").status_code == 200
        assert settle(client)["state"] == "done"


def test_listing_and_deleting_models(wizard: tuple[TestClient, FakeOllama, FakeCompat]) -> None:
    client, ollama, _ = wizard
    ollama._installed.append(InstalledModel("other:1b", 500, None))
    client.post("/api/setup/start", json={"model": REAL})
    settle(client)

    listed = {m["name"]: m for m in client.get("/api/setup/models").json()}
    assert listed[REAL]["active"] is True
    assert listed[REAL]["compat_ok"] is True
    assert listed["other:1b"]["active"] is False

    in_use = client.post("/api/setup/delete", json={"model": REAL})
    assert in_use.status_code == 409
    assert in_use.json()["code"] == "model_in_use"

    assert client.post("/api/setup/delete", json={"model": "other:1b"}).status_code == 200
    assert ollama.deleted == ["other:1b"]
