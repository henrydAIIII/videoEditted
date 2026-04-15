from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_standard_response():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "data": {"status": "ok", "service": "video-editted-backend"},
        "message": "success",
    }

