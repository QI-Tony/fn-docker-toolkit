from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings((tmp_path,))))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_all_pages_render(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings((tmp_path,))))

    for url in ("/", "/tools/empty-directories", "/tools/duplicates"):
        response = client.get(url)
        assert response.status_code == 200
        assert "NAS Toolbox" in response.text


def test_empty_directory_api_requires_scan_token_for_delete(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings((tmp_path,))))

    response = client.post(
        "/api/empty-directories/delete", json={"scan_token": "not-a-real-token"}
    )

    assert response.status_code == 409
