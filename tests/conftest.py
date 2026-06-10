import os
import ssl
import subprocess
import tempfile
import threading
from http.server import HTTPServer

import pytest

from tests.mock_dcache import MockDCacheHandler


@pytest.fixture(scope="function")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "ignore_https_errors": True}


@pytest.fixture(scope="session")
def mock_dcache():
    """Generate a self-signed cert for localhost so the mock can speak HTTPS."""
    cert_dir = tempfile.mkdtemp()
    cert_path = os.path.join(cert_dir, "mock.crt")
    key_path = os.path.join(cert_dir, "mock.key")
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            key_path,
            "-out",
            cert_path,
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )

    server = HTTPServer(("0.0.0.0", 9999), MockDCacheHandler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_path, key_path)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.last_token = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
