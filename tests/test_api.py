from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings((tmp_path,))))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_vue_single_page_app_renders_with_inlined_assets(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings((tmp_path,))))

    response = client.get("/")

    assert response.status_code == 200
    assert "NAS Toolbox" in response.text
    assert '<div id="app"></div>' in response.text
    assert "<style" in response.text
    assert "<script" in response.text
    assert "/assets/" not in response.text


def test_empty_directory_api_requires_scan_token_for_delete(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings((tmp_path,))))

    response = client.post(
        "/api/empty-directories/delete", json={"scan_token": "not-a-real-token"}
    )

    assert response.status_code == 409


def test_duplicate_api_supports_filename_strategy(tmp_path: Path) -> None:
    first = tmp_path / "one" / "same.txt"
    second = tmp_path / "two" / "same.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    client = TestClient(create_app(Settings((tmp_path,))))

    response = client.post(
        "/api/duplicates/scan",
        json={"path": str(tmp_path), "strategy": "filename"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy"] == "filename"
    assert payload["duplicate_groups"] == 1
    assert payload["groups"][0]["files"][0]["path"]
    assert payload["groups"][0]["confidence"] == "review"
