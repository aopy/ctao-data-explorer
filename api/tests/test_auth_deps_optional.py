from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api.auth.deps_optional import get_optional_identity


def test_optional_identity_invalid_token_returns_none(monkeypatch):
    from fastapi import HTTPException, status

    import api.auth.deps_optional as mod

    def fake_verify(_token: str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token")

    monkeypatch.setattr(mod, "verify_bearer", fake_verify)

    app = FastAPI()

    @app.get("/x")
    def x(ident=Depends(get_optional_identity)):
        return {"ident": ident is not None}

    client = TestClient(app)
    r = client.get("/x", headers={"Authorization": "Bearer bad"})
    assert r.status_code == 200
    assert r.json()["ident"] is False
