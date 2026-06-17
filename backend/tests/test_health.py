"""Basic health-check test (no database required)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["app"]
    assert body["version"]
    assert body["environment"]


def test_api_v1_root_is_mounted(client: TestClient) -> None:
    response = client.get("/api/v1/")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
