from __future__ import annotations

import base64
import json
import os
from http.server import BaseHTTPRequestHandler

FRONTEND_ORIGIN = (os.getenv("FRONTEND_URL") or "https://ctao-data-explorer.test.example").rstrip(
    "/"
)


class MockDCacheHandler(BaseHTTPRequestHandler):
    """Minimal dCache mock that validates bearer token JWT claims.

    Serves a static file for any GET with a non-empty Bearer token.
    Decodes the JWT payload and stores it on ``server.last_token``
    for test assertions.
    """

    def do_GET(self) -> None:
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"no token")
            return

        token = auth.removeprefix("Bearer ")
        try:
            _, payload_b64, _ = token.split(".")
            # Restore padding stripped by JWT encoding
            payload_b64 += "=" * (-len(payload_b64) % 4)
            claims: dict = json.loads(base64.urlsafe_b64decode(payload_b64))
        except Exception:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"invalid token")
            return

        self.server.last_token = claims  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Disposition", "attachment; filename=test-file.txt")
        self.send_header("Content-Type", "application/octet-stream")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(b"mock dcache content\n")

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", FRONTEND_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition, Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def log_message(self, fmt: str, *args: object) -> None:
        pass
