import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "content-type",
}


def preflight(client: TestClient, origin: str) -> dict[str, str]:
    response = client.options(
        "/health", headers={"Origin": origin, **PREFLIGHT_HEADERS}
    )
    return {"status": str(response.status_code), **response.headers}


def test_default_origin_is_allowed() -> None:
    result = preflight(TestClient(create_app(Settings())), "http://localhost:3000")

    assert result["status"] == "200"
    assert result["access-control-allow-origin"] == "http://localhost:3000"


def test_configured_origin_is_allowed_and_others_are_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, http://localhost:5173")
    client = TestClient(create_app(Settings()))

    allowed = preflight(client, "https://app.example.com")
    other_allowed = preflight(client, "http://localhost:5173")
    denied = preflight(client, "http://localhost:3000")

    assert allowed["status"] == "200"
    assert allowed["access-control-allow-origin"] == "https://app.example.com"
    assert other_allowed["access-control-allow-origin"] == "http://localhost:5173"
    assert denied["status"] == "400"
    assert "access-control-allow-origin" not in denied
