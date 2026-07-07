from fastapi.testclient import TestClient

from api.config import get_api_settings
from api.main import app


def test_frontend_config_endpoint():
    settings = get_api_settings()

    with TestClient(app) as client:
        response = client.get("/api/config/frontend")

    assert response.status_code == 200
    assert response.json() == {
        "default_tap_url": settings.DEFAULT_TAP_URL,
        "default_obscore_table": settings.DEFAULT_OBSCORE_TABLE,
    }
