from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth.deps import get_required_identity


def test_get_required_identity_no_auth_header_returns_401():
    app = FastAPI()

    @app.get("/x")
    def x(identity=Depends(get_required_identity)):
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/x")
    assert r.status_code == 401


def test_get_required_identity_invalid_token_returns_401(monkeypatch):
    from api.auth import deps

    def fake_verify(_token: str):
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

    monkeypatch.setattr(deps, "verify_bearer", fake_verify)

    app = FastAPI()

    @app.get("/x")
    def x(identity=Depends(get_required_identity)):
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/x", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 401
