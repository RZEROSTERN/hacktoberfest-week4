from fastapi.testclient import TestClient


def test_health_is_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_reports_no_model_before_setup(client: TestClient) -> None:
    body = client.get("/api/status").json()
    assert body["vision_model"] is None
    # Sensitive text is not indexed until the user turns it on.
    assert body["index_sensitive_text"] is False
