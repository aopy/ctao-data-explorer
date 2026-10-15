"""Ephemeral HTTPS storage mock for the k6 Helm test pod."""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response

app = FastAPI()
_BLOBS = (b"x" * 1024, b"x" * 8192, b"x" * 65536)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/objects/{obs_id}")
async def object_blob(obs_id: int, authorization: str | None = Header(default=None)) -> Response:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    blob = _BLOBS[obs_id % len(_BLOBS)]
    return Response(
        blob,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{obs_id}.fits"',
            "X-Mock-Blob-Size": str(len(blob)),
        },
    )


def _certificate(directory: Path) -> tuple[Path, Path]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


if __name__ == "__main__":
    cert_dir = Path(os.getenv("MOCK_STORAGE_TLS_DIR", tempfile.mkdtemp()))
    cert_dir.mkdir(parents=True, exist_ok=True)
    certfile, keyfile = _certificate(cert_dir)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9999,
        ssl_certfile=certfile,
        ssl_keyfile=keyfile,
        access_log=False,
    )
