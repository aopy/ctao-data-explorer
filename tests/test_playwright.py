import logging
import os
import re

import pytest
from playwright.sync_api import Page, expect

frontend_url = os.getenv("FRONTEND_URL")

SCREENSHOTS_DIR = "/tmp/screenshots"
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def _login(page: Page):
    """Login helper for tests that require an authenticated session.

    Clicks the Login button, fills in TEST_USER and TEST_PASSWORD on the IAM login form,
    submits, handles the IAM consent/approval page if it appears, and waits for the
    redirect back to the frontend.
    Skips if credentials are not set.
    """
    test_user = os.getenv("TEST_USER")
    test_password = os.getenv("TEST_PASSWORD")
    if not test_user or not test_password:
        pytest.skip("TEST_USER/TEST_PASSWORD not configured, skipping login test for now")
    login_button = page.get_by_role("button", name="Login", exact=True)
    expect(login_button).to_be_visible()
    login_button.click()
    page.wait_for_load_state("networkidle")
    expect(page.locator("#username")).to_be_visible()
    page.locator("#username").fill(test_user)
    page.locator("#password").fill(test_password)
    page.screenshot(path=f"{SCREENSHOTS_DIR}/login_before_submit.png")
    with page.expect_navigation(timeout=60000):
        page.get_by_role("button", name="Sign in", exact=True).click()
    page.screenshot(path=f"{SCREENSHOTS_DIR}/login_at_callback.png")
    # If the page is still on the IAM host, a consent/approval page is shown.
    # Click the approve button to complete the authorization flow.
    if "iam-ctao-data-explorer" in page.url:
        approve_button = page.get_by_role("button", name="Authorize", exact=True)
        expect(approve_button).to_be_visible(timeout=10000)
        with page.expect_navigation(timeout=60000):
            approve_button.click()
    # The callback redirects (307) to the frontend, so expect_navigation above
    # already follows it. Just wait for the actual frontend page to be fully loaded.
    if not page.url.startswith(frontend_url):
        page.wait_for_url(f"{frontend_url}**", timeout=60000)
    page.wait_for_load_state("networkidle")
    page.screenshot(path=f"{SCREENSHOTS_DIR}/login_after_redirect.png")


@pytest.mark.verifies_usecase("SUSS-UC-050-19")
def test_login(page: Page):
    """Authenticate via IAM and verify restricted tabs appear after login.

    Navigates to the frontend, confirms restricted tabs (My Basket, Preview Jobs, etc.)
    are absent initially, calls _login to authenticate via IAM, then checks all restricted
    tabs are visible in the navigation bar after successful login.
    """
    page.goto(frontend_url, wait_until="networkidle")
    for tab in ["My Basket", "Preview Jobs", "Query Store", "Profile"]:
        expect(page.get_by_role("link", name=tab, exact=True)).to_have_count(0)
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_login_before.png")
    _login(page)
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_login_after.png")
    for tab in ["Search", "Results", "My Basket", "Preview Jobs", "Query Store", "Profile"]:
        expect(page.get_by_role("link", name=tab, exact=True)).to_be_visible()


@pytest.mark.verifies_usecase("SUSS-UC-050-20")
def test_logout(page: Page):
    """Log out and verify restricted tabs are no longer visible.

    Logs in, confirms restricted tabs are visible, clicks Logout, waits for
    redirect back to frontend, then verifies restricted tabs (My Basket, Preview Jobs, etc.)
    are hidden while public tabs (Search, Results) remain visible.
    """
    page.goto(frontend_url, wait_until="networkidle")
    _login(page)
    for tab in ["Search", "Results", "My Basket", "Preview Jobs", "Query Store", "Profile"]:
        expect(page.get_by_role("link", name=tab, exact=True)).to_be_visible()
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_logout_logged_in.png")
    logout_button = page.get_by_role("button", name="Logout", exact=True)
    expect(logout_button).to_be_visible()
    logout_button.click()
    page.wait_for_load_state("networkidle")
    if not page.url.startswith(frontend_url):
        page.wait_for_url(f"{frontend_url}**")
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_logout_after.png")
    for tab in ["My Basket", "Preview Jobs", "Query Store", "Profile"]:
        expect(page.get_by_role("link", name=tab, exact=True)).to_have_count(0)
    expect(page.get_by_role("link", name="Search", exact=True)).to_be_visible()
    expect(page.get_by_role("link", name="Results", exact=True)).to_be_visible()


@pytest.mark.verifies_usecase("SUSS-UC-050-19")
def test_csrf_cookie_set_after_login(page: Page):
    """Check that the XSRF-TOKEN cookie is absent before login and set afterwards.

    Reads browser cookies before login and asserts XSRF-TOKEN is absent. After login via
    _login, reads cookies again and asserts XSRF-TOKEN is present and non-empty.
    """
    page.goto(frontend_url, wait_until="networkidle")
    cookies = page.context.cookies()
    xsrf_before = [c for c in cookies if c["name"] == "XSRF-TOKEN"]
    assert len(xsrf_before) == 0, "XSRF-TOKEN should not be set before login"
    _login(page)
    cookies = page.context.cookies()
    xsrf = [c for c in cookies if c["name"] == "XSRF-TOKEN"]
    assert len(xsrf) == 1, "XSRF-TOKEN must be set after login"
    assert len(xsrf[0]["value"]) > 0, "XSRF-TOKEN must be non-empty"


@pytest.mark.verifies_usecase("SUSS-UC-050-15")
def test_authenticated_basket_add(page: Page):
    """Login, search for target, add to basket, and verify it appears in My Basket tab.

    Logs in, navigates to My Basket to trigger default basket creation, searches for "crab",
    clicks the Add button on the first result row, checks for the feedback alert,
    then navigates to My Basket and verifies the observation is listed.
    """
    page.goto(frontend_url, wait_until="networkidle")
    _login(page)
    # Visit My Basket first to trigger auto-creation of the default "Basket 1" group,
    # so the Add buttons are enabled on the search results page.
    my_basket_link = page.get_by_role("link", name="My Basket", exact=True)
    expect(my_basket_link).to_be_visible()
    my_basket_link.click()
    page.wait_for_load_state("networkidle")

    # Confirm basket was actually created before navigating away
    expect(page.get_by_role("textbox", name="Current basket name")).to_have_value("Basket 1")

    # Navigate back to search
    search_link = page.get_by_role("link", name="Search", exact=True)
    expect(search_link).to_be_visible()
    search_link.click()
    page.wait_for_load_state("networkidle")

    source_input = page.locator("#objectNameInput")
    expect(source_input).to_be_visible()
    source_input.fill("crab")

    resolve_button = page.get_by_role("button", name="Resolve", exact=True)
    expect(resolve_button).to_be_visible()
    resolve_button.click()
    expect(page.locator("#coord1Input")).not_to_have_value("")
    expect(page.locator("#coord2Input")).not_to_have_value("")

    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_enabled()
    search_button.click()
    page.wait_for_load_state("networkidle")

    # Wait for at least one result row before touching Add
    expect(page.locator("table tbody tr").first).to_be_visible()

    # Add button has no title attribute — match by role + name
    add_btn = page.get_by_role("button", name="Add", exact=True).first
    expect(add_btn).to_be_enabled()
    add_btn.click()

    alert = page.locator(".alert")
    expect(alert).to_be_visible()
    page.screenshot(path=f"{SCREENSHOTS_DIR}/basket_add_alert.png")

    # Navigate to My Basket and verify the observation appears in the list
    my_basket_link = page.get_by_role("link", name="My Basket", exact=True)
    my_basket_link.click()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text(re.compile(r"Obs\. id:"), exact=False)).to_be_visible()
    page.screenshot(path=f"{SCREENSHOTS_DIR}/basket_after_add.png")


@pytest.mark.verifies_usecase("SUSS-UC-050-01")
def test_query_by_object_name(page: Page):
    page.goto(frontend_url, wait_until="networkidle")

    logging.info(f"Page title: {page.title()}")
    assert "CTAO Data Explorer" in page.title()

    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_1_before.png")

    # Fill source name and resolve
    source_input = page.locator("#objectNameInput")
    expect(source_input).to_be_visible()
    source_input.fill("crab")

    resolve_button = page.get_by_role("button", name="Resolve", exact=True)
    expect(resolve_button).to_be_visible()
    resolve_button.click()

    # Wait until resolve has populated coordinates
    coord1_input = page.locator("#coord1Input")
    coord2_input = page.locator("#coord2Input")
    expect(coord1_input).not_to_have_value("")
    expect(coord2_input).not_to_have_value("")

    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_2_resolve.png")

    # Click the main submit button
    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_visible()
    expect(search_button).to_be_enabled()
    search_button.click()

    # Wait for some post-search UI stability
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_3_search.png")


@pytest.mark.xfail
@pytest.mark.verifies_usecase("SUSS-UC-050-02")
def test_query_by_sky_coordinates():
    raise NotImplementedError("Should be implemented for this release")


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_datalink_download_visible(page: Page):
    page.goto(frontend_url, wait_until="networkidle")

    # Resolve source
    source_input = page.locator("#objectNameInput")
    expect(source_input).to_be_visible()
    source_input.fill("crab")

    resolve_button = page.get_by_role("button", name="Resolve", exact=True)
    resolve_button.click()

    expect(page.locator("#coord1Input")).not_to_have_value("")
    expect(page.locator("#coord2Input")).not_to_have_value("")

    # Run search
    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_enabled()
    search_button.click()
    page.wait_for_load_state("networkidle")

    # DataLink services must be available (not "No services available")
    no_services = page.get_by_text("No services available")
    expect(no_services).to_have_count(0)

    # At least one download/datalink element must be visible
    datalink_links = page.locator("[data-testid='datalink-url']")

    # Click the first row's DataLink toggle
    page.locator("[data-testid='datalink-toggle']").first.click()
    page.wait_for_timeout(1000)  # wait 1 sec
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_4_datalink_before_assert.png")
    expect(page.locator("[data-testid='datalink-no-services']")).to_have_count(0)
    expect(datalink_links.first).to_be_visible()
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_5_datalink.png")
