import io

import respx
from fastapi.testclient import TestClient
from httpx import Response

from app.main import app

client = TestClient(app)


def _upload_files():
    return {"video": ("clip.mp4", io.BytesIO(b"fake video bytes"), "video/mp4")}


@respx.mock
def test_create_variation_uses_task_submit_and_poll(monkeypatch):
    monkeypatch.setattr("app.main.SEEDANCE_API_KEY", "test-key")
    monkeypatch.setattr("app.main.SEEDANCE_API_URL", "https://ark.example/api/v3")

    create_route = respx.post("https://ark.example/api/v3/contents/generations/tasks").mock(
        return_value=Response(200, json={"id": "task-123"})
    )
    poll_route = respx.get("https://ark.example/api/v3/contents/generations/tasks/task-123").mock(
        return_value=Response(200, json={"status": "succeeded", "content": {"video_url": "https://cdn.example/out.mp4"}})
    )
    respx.get("https://cdn.example/out.mp4").mock(return_value=Response(200, content=b"generated video bytes"))

    response = client.post(
        "/api/variations",
        data={"prompt": "Cinematic showcase", "style": "Cinematic"},
        files=_upload_files(),
    )

    assert response.status_code == 200
    body = response.json()
    assert "Generated with Seedance" in " ".join(body["notes"])
    assert create_route.called
    assert poll_route.called


@respx.mock
def test_create_variation_falls_back_when_task_fails(monkeypatch):
    monkeypatch.setattr("app.main.SEEDANCE_API_KEY", "test-key")
    monkeypatch.setattr("app.main.SEEDANCE_API_URL", "https://ark.example/api/v3")

    respx.post("https://ark.example/api/v3/contents/generations/tasks").mock(
        return_value=Response(200, json={"id": "task-123"})
    )
    respx.get("https://ark.example/api/v3/contents/generations/tasks/task-123").mock(
        return_value=Response(200, json={"status": "failed", "error": {"message": "bad prompt"}})
    )

    response = client.post(
        "/api/variations",
        data={"prompt": "Cinematic showcase", "style": "Cinematic"},
        files=_upload_files(),
    )

    assert response.status_code == 200
    body = response.json()
    assert any("failed" in note.lower() or "fallback" in note.lower() for note in body["notes"])


def test_create_variation_skips_seedance_when_no_key(monkeypatch):
    monkeypatch.setattr("app.main.SEEDANCE_API_KEY", "")

    response = client.post(
        "/api/variations",
        data={"prompt": "Cinematic showcase", "style": "Cinematic"},
        files=_upload_files(),
    )

    assert response.status_code == 200
    body = response.json()
    assert not any("Seedance" in note for note in body["notes"])
