"""Create one real BFF session for the k6 Helm test pod."""

import json
import os
from pathlib import Path

import pytest
from ctao_shared.constants import COOKIE_NAME_MAIN_SESSION, COOKIE_NAME_XSRF
from playwright.sync_api import Page, expect


@pytest.mark.skipif(not os.getenv("LOAD_TEST_BFF_BOOTSTRAP"), reason="k6 BFF bootstrap only")
def test_create_bff_session_for_k6(page: Page):
    """Create the BFF session used by k6.

    1. Open the frontend and start the BFF OIDC login.
    2. Authenticate the configured IAM test user.
    3. Acquire the BFF-issued XSRF cookie.
    4. Store only the BFF session and XSRF cookies for k6.
    """
    frontend_url = os.environ["FRONTEND_URL"]
    output = Path(os.environ["BFF_SESSION_FILE"])

    page.goto(frontend_url, wait_until="networkidle")
    page.get_by_role("button", name="Login", exact=True).click()
    expect(page.locator("#username")).to_be_visible()

    page.locator("#username").fill(os.environ["TEST_USER"])
    page.locator("#password").fill(os.environ["TEST_PASSWORD"])
    with page.expect_navigation(timeout=60_000):
        page.get_by_role("button", name="Sign in", exact=True).click()
    if "iam-ctao-data-explorer" in page.url:
        with page.expect_navigation(timeout=60_000):
            page.get_by_role("button", name="Authorize", exact=True).click()
    page.wait_for_url(f"{frontend_url}**", timeout=60_000)

    status = page.evaluate(
        """async () => (await fetch('/auth/me', { credentials: 'include' })).status"""
    )
    assert status == 200

    cookies = {item["name"]: item["value"] for item in page.context.cookies()}
    assert cookies.get(COOKIE_NAME_MAIN_SESSION)
    assert cookies.get(COOKIE_NAME_XSRF)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "session": cookies[COOKIE_NAME_MAIN_SESSION],
                "xsrf": cookies[COOKIE_NAME_XSRF],
            }
        )
    )
