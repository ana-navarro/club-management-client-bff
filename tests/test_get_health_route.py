from fastapi.testclient import TestClient

from src.main import app


def test_get_health_responds_with_the_service_status() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
