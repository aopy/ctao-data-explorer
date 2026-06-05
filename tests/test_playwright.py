import logging
import os
import re

import allure
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

    Steps:
    1. Navigate to the frontend.
    2. Assert restricted tabs (My Basket, Preview Jobs, etc.) are absent initially.
    3. Call _login to authenticate via IAM.
    4. Assert all tabs (Search, Results, My Basket, Preview Jobs, Query Store, Profile)
       are visible after successful login.
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

    Steps:
    1. Log in via _login helper.
    2. Assert all tabs are visible after login.
    3. Click the Logout button.
    4. Assert restricted tabs (My Basket, Preview Jobs, etc.) are hidden.
    5. Assert public tabs (Search, Results) remain visible.
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

    Steps:
    1. Navigate to frontend and read browser cookies.
    2. Assert XSRF-TOKEN is absent before login.
    3. Call _login to authenticate.
    4. Read cookies again.
    5. Assert XSRF-TOKEN is present and non-empty after login.
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


@pytest.mark.verifies_usecase("SUSS-UC-050-11")
def test_authenticated_basket_add(page: Page):
    """Login, search for target, add to basket, and verify it appears in My Basket tab.

    Steps:
    1. Navigate to frontend and log in via _login helper.
    2. Visit My Basket first to trigger auto-creation of default "Basket 1".
    3. Return to Search, enter "crab", resolve coordinates, and click Search.
    4. Wait for search results to load.
    5. Click the Add button on the first result row.
    6. Assert an .alert-info success message confirms the addition.
    7. Navigate to My Basket and assert the observation appears in the list.
    """
    page.goto(frontend_url, wait_until="networkidle")
    _login(page)
    my_basket_link = page.get_by_role("link", name="My Basket", exact=True)
    expect(my_basket_link).to_be_visible()
    my_basket_link.click()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_role("textbox", name="Current basket name")).to_have_value("Basket 1")

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

    add_btn = page.get_by_role("button", name="Add", exact=True).first
    expect(add_btn).to_be_enabled()
    add_btn.click()

    alert = page.locator(".alert-info")
    expect(alert).to_be_visible()
    expect(alert).to_contain_text("added to active basket successfully!")
    page.screenshot(path=f"{SCREENSHOTS_DIR}/basket_add_alert.png")

    my_basket_link = page.get_by_role("link", name="My Basket", exact=True)
    my_basket_link.click()
    page.wait_for_load_state("networkidle")
    expect(page.get_by_text(re.compile(r"Obs\. id:"), exact=False)).to_be_visible()
    page.screenshot(path=f"{SCREENSHOTS_DIR}/basket_after_add.png")


@pytest.mark.verifies_usecase("SUSS-UC-050-01")
def test_query_by_object_name(page: Page):
    """Query observations by astronomical object name and verify results are shown.

    Steps:
    1. Navigate to the frontend.
    2. Assert the page title contains "CTAO Data Explorer".
    3. Enter "crab" in the object name input and click Resolve.
    4. Assert coordinates are populated after resolution.
    5. Click Search.
    6. Assert the URL navigates to the /results page.
    7. Assert no warning/error message is displayed.
    """
    with allure.step("Navigate to frontend and verify title"):
        page.goto(frontend_url, wait_until="networkidle")

        logging.info(f"Page title: {page.title()}")

        assert "CTAO Data Explorer" in page.title()

        fn = f"{SCREENSHOTS_DIR}/test_frontend_screenshot_1_initial.png"
        page.screenshot(path=fn)

        allure.attach(
            page.screenshot(path=fn),
            name="Initial Page",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Fill in object name and resolve to coordinates"):
        source_input = page.locator("#objectNameInput")
        expect(source_input).to_be_visible()
        source_input.fill("crab")

        resolve_button = page.get_by_role("button", name="Resolve", exact=True)
        expect(resolve_button).to_be_visible()
        resolve_button.click()

        coord1_input = page.locator("#coord1Input")
        coord2_input = page.locator("#coord2Input")
        expect(coord1_input).not_to_have_value("")
        expect(coord2_input).not_to_have_value("")

        fn = f"{SCREENSHOTS_DIR}/test_frontend_screenshot_2_resolve.png"
        page.screenshot(path=fn)
        allure.attach(
            page.screenshot(path=fn),
            name="Resolved Coordinates",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search and verify results"):
        search_button = page.get_by_role("button", name="Search", exact=True)
        expect(search_button).to_be_visible()
        expect(search_button).to_be_enabled()
        search_button.click()

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

        assert "/results" in page.url, "Expected to navigate to /results after search"
        expect(page.locator(".alert-warning")).to_have_count(0)

        fn = f"{SCREENSHOTS_DIR}/test_frontend_screenshot_3_search.png"
        page.screenshot(path=fn)
        allure.attach(
            page.screenshot(path=fn),
            name="Search Results",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-01")
def test_query_by_object_name_ned(page: Page):
    """Query observations by object name resolved via NED and verify results.

    Steps:
    1. Navigate to the frontend.
    2. Uncheck SIMBAD, check NED as resolution service.
    3. Enter "Mrk 501" in the object name input and click Resolve.
    4. Assert coordinates are populated to RA=253.467569, Dec=39.760169.
    5. Click Search.
    6. Assert the URL navigates to the /results page.
    7. Assert no warning/error message is displayed.
    """
    page.goto(frontend_url, wait_until="networkidle")
    page.locator("#useSimbadCheck").uncheck()
    page.locator("#useNedCheck").check()
    page.locator("#objectNameInput").fill("Mrk 501")
    resolve_button = page.get_by_role("button", name="Resolve", exact=True)
    expect(resolve_button).to_be_visible()
    resolve_button.click()
    coord1_input = page.locator("#coord1Input")
    coord2_input = page.locator("#coord2Input")
    expect(coord1_input).to_have_value("253.467569")
    expect(coord2_input).to_have_value("39.760169")
    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_enabled()
    search_button.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    assert "/results" in page.url, "Expected to navigate to /results after search"
    expect(page.locator(".alert-warning")).to_have_count(0)


@pytest.mark.verifies_usecase("SUSS-UC-050-02")
def test_query_by_sky_coordinates(page: Page):
    """Query observations by sky coordinates and verify results are shown.

    Steps:
    1. Navigate to the frontend.
    2. Enter RA=83.63, Dec=22.01 (Crab Nebula), radius=3 deg.
    3. Click Search.
    4. Assert the URL navigates to the /results page.
    5. Assert no warning/error message is displayed.
    """
    page.goto(frontend_url, wait_until="networkidle")
    page.locator("#coord1Input").fill("83.63")
    page.locator("#coord2Input").fill("22.01")
    page.locator("#radiusInput").fill("3")
    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_enabled()
    search_button.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)
    assert "/results" in page.url, "Expected to navigate to /results after search"
    expect(page.locator(".alert-warning")).to_have_count(0)


@pytest.mark.verifies_usecase("SUSS-UC-050-06")
def test_no_results_warning(page: Page):
    """Search with coordinates that match no observations and verify the warning message.

    Steps:
    1. Navigate to the frontend.
    2. Enter RA=0, Dec=0, radius=0.01 deg (no observations there).
    3. Click Search.
    4. Assert an .alert-warning message displays:
       "No results were found for the given search criteria."
    """
    page.goto(frontend_url, wait_until="networkidle")
    page.locator("#coord1Input").fill("0")
    page.locator("#coord2Input").fill("0")
    page.locator("#radiusInput").fill("0.01")
    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_enabled()
    search_button.click()
    page.wait_for_load_state("networkidle")
    alert = page.locator(".alert-warning")
    expect(alert).to_be_visible()
    expect(alert).to_contain_text("No results were found for the given search criteria.")


@pytest.mark.verifies_usecase("SUSS-UC-050-09")
def test_download_single_product(page: Page):
    """Search and verify the download button is available for a single observation.

    Steps:
    1. Navigate to the frontend.
    2. Enter "crab", resolve coordinates via SIMBAD.
    3. Assert coordinates are populated after resolution.
    4. Click Search and wait for results.
    5. Assert at least one [data-testid='download-button'] is visible,
       confirming the single-file download action is exposed.
    """
    page.goto(frontend_url, wait_until="networkidle")

    source_input = page.locator("#objectNameInput")
    expect(source_input).to_be_visible()
    source_input.fill("crab")

    resolve_button = page.get_by_role("button", name="Resolve", exact=True)
    expect(resolve_button).to_be_visible()
    resolve_button.click()

    expect(page.locator("#coord1Input")).not_to_have_value("")
    expect(page.locator("#coord2Input")).not_to_have_value("")

    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_visible()
    expect(search_button).to_be_enabled()
    search_button.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_4_download_before_assert.png")

    download_buttons = page.locator("[data-testid='download-button']")
    expect(download_buttons.first).to_be_visible()

    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_frontend_screenshot_5_download.png")


@pytest.mark.verifies_usecase("SUSS-UC-050-21")
def test_view_user_profile(page: Page):
    """Log in and verify the user profile page displays correct user information.

    Steps:
    1. Navigate to the frontend and log in via _login helper.
    2. Click the Profile navigation link.
    3. Assert the profile card (.card-body) is visible.
    4. Assert the user's name "SDC User" is displayed.
    5. Assert the user's email "sdc@test.example" is displayed.
    """
    page.goto(frontend_url, wait_until="networkidle")
    _login(page)
    profile_link = page.get_by_role("link", name="Profile", exact=True)
    expect(profile_link).to_be_visible()
    profile_link.click()
    page.wait_for_load_state("networkidle")
    page.screenshot(path=f"{SCREENSHOTS_DIR}/test_profile.png")
    expect(page.locator(".card-body")).to_be_visible()
    expect(page.get_by_text(re.compile(r"Name:\s*SDC User"))).to_be_visible()
    expect(page.get_by_text(re.compile(r"Email:\s*sdc@test\.example"))).to_be_visible()
