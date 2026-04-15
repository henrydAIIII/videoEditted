import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


client = TestClient(app)


def test_upload_saves_assets_and_job_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_EDITTED_ASSETS_DIR", str(tmp_path / "assets"))
    get_settings.cache_clear()

    files = {
        "ppt_video": ("deck.mp4", b"ppt-content", "video/mp4"),
        "speaker_video": ("speaker.mp4", b"speaker-content", "video/mp4"),
        "subtitles": ("captions.srt", b"1\n00:00:00,000 --> 00:00:01,000\nhello\n", "application/x-subrip"),
    }

    response = client.post("/api/upload", files=files)

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    assert payload["message"] == "upload success"
    assert payload["data"]["stage"] == "pending"

    job_id = payload["data"]["job_id"]
    job_dir = tmp_path / "assets" / job_id

    assert (job_dir / "ppt_video.mp4").read_bytes() == b"ppt-content"
    assert (job_dir / "speaker_video.mp4").read_bytes() == b"speaker-content"
    assert (job_dir / "subtitles.srt").read_text(encoding="utf-8").startswith("1\n00:00:00,000")

    metadata = json.loads((job_dir / "job.json").read_text(encoding="utf-8"))
    assert metadata["job_id"] == job_id
    assert metadata["status"] == "pending"
    assert metadata["files"] == {
        "ppt_video": "ppt_video.mp4",
        "speaker_video": "speaker_video.mp4",
        "subtitles": "subtitles.srt",
    }

    get_settings.cache_clear()
