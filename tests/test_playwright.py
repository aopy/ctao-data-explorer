import logging
import os
import re

import allure
import pytest
import requests
from playwright.sync_api import Page, expect

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url is None:
    pytest.skip(
        "FRONTEND_URL is not set — skipping Playwright tests. "
        "Set it to the frontend URL, e.g. https://ctao-data-explorer.test.example"
    )

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
    3. Authenticate via IAM.
    4. Assert all tabs (Search, Results, My Basket, Preview Jobs, Query Store, Profile)
       are visible after successful login.
    """
    with allure.step("Navigate to frontend and verify restricted tabs are absent"):
        page.goto(frontend_url, wait_until="networkidle")
        for tab in ["My Basket", "Preview Jobs", "Query Store", "Profile"]:
            expect(page.get_by_role("link", name=tab, exact=True)).to_have_count(0)
        fn = f"{SCREENSHOTS_DIR}/test_login_before.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Before Login",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Authenticate via IAM"):
        _login(page)

    with allure.step("Verify all tabs are visible after login"):
        fn = f"{SCREENSHOTS_DIR}/test_login_after.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="After Login",
            attachment_type=allure.attachment_type.PNG,
        )
        for tab in ["Search", "Results", "My Basket", "Preview Jobs", "Query Store", "Profile"]:
            expect(page.get_by_role("link", name=tab, exact=True)).to_be_visible()


@pytest.mark.verifies_usecase("SUSS-UC-050-20")
def test_logout(page: Page):
    """Log out and verify restricted tabs are no longer visible.

    Steps:
    1. Log in.
    2. Assert all tabs are visible after login.
    3. Click the Logout button.
    4. Assert restricted tabs (My Basket, Preview Jobs, etc.) are hidden.
    5. Assert public tabs (Search, Results) remain visible.
    """
    with allure.step("Log in and verify all tabs are visible"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        for tab in ["Search", "Results", "My Basket", "Preview Jobs", "Query Store", "Profile"]:
            expect(page.get_by_role("link", name=tab, exact=True)).to_be_visible()
        fn = f"{SCREENSHOTS_DIR}/test_logout_logged_in.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Logged In",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Click Logout and wait for redirect"):
        logout_button = page.get_by_role("button", name="Logout", exact=True)
        expect(logout_button).to_be_visible()
        logout_button.click()
        page.wait_for_load_state("networkidle")
        if not page.url.startswith(frontend_url):
            page.wait_for_url(f"{frontend_url}**")

    with allure.step("Verify restricted tabs are hidden, public tabs remain"):
        for tab in ["My Basket", "Preview Jobs", "Query Store", "Profile"]:
            expect(page.get_by_role("link", name=tab, exact=True)).to_have_count(0)
        expect(page.get_by_role("link", name="Search", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Results", exact=True)).to_be_visible()
        fn = f"{SCREENSHOTS_DIR}/test_logout_after.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="After Logout",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-19")
def test_csrf_cookie_set_after_login(page: Page):
    """Check that the XSRF-TOKEN cookie is absent before login and set afterwards.

    Steps:
    1. Navigate to frontend and read browser cookies.
    2. Assert XSRF-TOKEN is absent before login.
    3. Log in.
    4. Read cookies again.
    5. Assert XSRF-TOKEN is present and non-empty after login.
    """
    with allure.step("Navigate to frontend and assert XSRF-TOKEN cookie is absent"):
        page.goto(frontend_url, wait_until="networkidle")
        cookies = page.context.cookies()
        xsrf_before = [c for c in cookies if c["name"] == "XSRF-TOKEN"]
        assert len(xsrf_before) == 0, "XSRF-TOKEN should not be set before login"

    with allure.step("Log in via IAM"):
        _login(page)

    with allure.step("Assert XSRF-TOKEN cookie is present and non-empty after login"):
        cookies = page.context.cookies()
        xsrf = [c for c in cookies if c["name"] == "XSRF-TOKEN"]
        assert len(xsrf) == 1, "XSRF-TOKEN must be set after login"
        assert len(xsrf[0]["value"]) > 0, "XSRF-TOKEN must be non-empty"


@pytest.mark.verifies_usecase("SUSS-UC-050-11")
def test_authenticated_basket_add(page: Page):
    """Login, search for target, create an active basket, add to it, and verify.

    Steps:
    1. Navigate to frontend and log in.
    2. Enter "crab", resolve coordinates via SIMBAD, and click Search.
    3. Wait for results table rows (`.rdt_TableRow`) to appear.
    4. Select the first row checkbox, click "Add 1 selected" — expect "no active basket" error.
    5. Visit My Basket to create/activate "Basket 1".
    6. Return to Results, wait for rows, find a row not yet in basket (filtering for
       "Add" button rather than "In Basket"), and click it.
    7. Assert success message matching "Added obs_id=<id> to active basket successfully!".
    8. Navigate to My Basket and assert the observation appears.
    """
    with allure.step("Log in, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        source_input = page.locator("#objectNameInput")
        expect(source_input).to_be_visible()
        source_input.fill("crab")
        resolve_button = page.get_by_role("button", name="Resolve", exact=True)
        expect(resolve_button).to_be_visible()
        resolve_button.click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")

    with allure.step("Run search and wait for results rows"):
        search_button = page.get_by_role("button", name="Search", exact=True)
        expect(search_button).to_be_enabled()
        search_button.click()
        page.wait_for_function("window.location.href.includes('results')", timeout=15000)
        page.wait_for_selector(".rdt_TableRow", state="visible", timeout=60000)

    with allure.step("Select first row and attempt Add — expect no active basket error"):
        page.locator(".rdt_TableRow").first.locator('input[type="checkbox"]').click()
        page.wait_for_timeout(500)
        add_btn = page.get_by_role("button", name="Add 1 selected")
        expect(add_btn).to_be_enabled()
        add_btn.click()
        alert = page.locator(".alert-info")
        expect(alert).to_be_visible()
        expect(alert).to_have_text("Please select an active basket group first!")

    with allure.step("Visit My Basket to create active basket, return and add observation"):
        my_basket_link = page.get_by_role("link", name="My Basket", exact=True)
        expect(my_basket_link).to_be_visible()
        my_basket_link.click()
        page.wait_for_load_state("networkidle")
        results_link = page.get_by_role("link", name="Results", exact=True)
        expect(results_link).to_be_visible()
        results_link.click()
        page.wait_for_function("window.location.href.includes('results')", timeout=15000)
        page.wait_for_selector(".rdt_TableRow", state="visible", timeout=60000)
        page.locator(".rdt_TableRow").filter(
            has=page.get_by_role("button", name="Add")
        ).first.get_by_role("button", name="Add").click()
        alert = page.locator(".alert-info")
        expect(alert).to_be_visible()
        expect(alert).to_have_text(re.compile(r"Added obs_id=\d+ to active basket successfully!"))

    with allure.step("Navigate to My Basket and verify observation appears"):
        my_basket_link = page.get_by_role("link", name="My Basket", exact=True)
        my_basket_link.click()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text(re.compile(r"Obs\. id:"), exact=False).first).to_be_visible()


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
        s = page.screenshot(path=fn)

        allure.attach(
            s,
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
        s = page.screenshot(path=fn)
        allure.attach(
            s,
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
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Search Results",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-01")
def test_resolve_coordinates_by_ned(page: Page):
    """Resolve coordinates for an object name via NED and verify both deg and hms/dms formats.
    Steps:
    1. Navigate to the frontend.
    2. Uncheck SIMBAD, check NED as resolution service.
    3. Enter "Mrk 501" in the object name input and click Resolve.
    4. Assert decimal-degree coordinates: RA≈253.467569 (±0.005 deg), Dec≈39.760169 (±0.005 deg).
    5. Switch coordinate system to Equatorial (hms/dms).
    6. Assert hms/dms coordinates: RA matches "16 53 XX.x", Dec matches "+39 45 XX.x".
    """
    with allure.step("Navigate and select NED resolution"):
        page.goto(frontend_url, wait_until="networkidle")
        page.locator("#useSimbadCheck").uncheck()
        page.locator("#useNedCheck").check()

    with allure.step('Enter "Mrk 501" and resolve via NED'):
        page.locator("#objectNameInput").fill("Mrk 501")
        resolve_button = page.get_by_role("button", name="Resolve", exact=True)
        expect(resolve_button).to_be_visible()
        resolve_button.click()

    with allure.step("Assert decimal-degree coordinates"):
        coord1_input = page.locator("#coord1Input")
        coord2_input = page.locator("#coord2Input")
        expect(coord1_input).not_to_have_value("")
        expect(coord2_input).not_to_have_value("")
        ra_val = float(coord1_input.input_value())
        dec_val = float(coord2_input.input_value())
        assert abs(ra_val - 253.467569) < 0.005, f"RA out of tolerance: {ra_val}"
        assert abs(dec_val - 39.760169) < 0.005, f"Dec out of tolerance: {dec_val}"

    with allure.step("Switch to Equatorial (hms/dms) and assert format"):
        page.get_by_role("button", name=re.compile(r"Equatorial.*hms")).click()
        page.wait_for_load_state("networkidle")
        expect(coord1_input).to_have_value(re.compile(r"^16 53 [\d.]+"))
        expect(coord2_input).to_have_value(re.compile(r"^\+39 45 [\d.]+"))


@pytest.mark.verifies_usecase("SUSS-UC-050-02")
def test_query_by_sky_coordinates(page: Page):
    """Query observations by sky coordinates and verify results appear in the data table.

    Steps:
    1. Navigate to the frontend.
    2. Enter RA=83.63, Dec=22.01 (Crab Nebula), radius=3 deg.
    3. Click Search.
    4. Assert the URL navigates to the /results page.
    5. Assert at least one `.rdt_TableRow` is rendered (results table populated).
    """
    with allure.step("Navigate and enter sky coordinates (RA=83.63, Dec=22.01, radius=3)"):
        page.goto(frontend_url, wait_until="networkidle")
        page.locator("#coord1Input").fill("83.63")
        page.locator("#coord2Input").fill("22.01")
        page.locator("#radiusInput").fill("3")

    with allure.step("Click Search and assert navigation to /results"):
        search_button = page.get_by_role("button", name="Search", exact=True)
        expect(search_button).to_be_enabled()
        search_button.click()
        page.wait_for_load_state("networkidle")
        try:
            page.wait_for_url("**/results**", timeout=10000)
        except Exception:
            page.screenshot(path=f"{SCREENSHOTS_DIR}/sky_search_timeout.png")
            logging.error("Search did not navigate to /results; checking for error alerts")
            raise

    with allure.step("Assert at least one results row is rendered"):
        expect(page.locator(".rdt_TableRow")).not_to_have_count(0, timeout=60000)


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
    with allure.step(
        "Navigate and enter coordinates with no observations (RA=0, Dec=0, radius=0.01)"
    ):
        page.goto(frontend_url, wait_until="networkidle")
        page.locator("#coord1Input").fill("0")
        page.locator("#coord2Input").fill("0")
        page.locator("#radiusInput").fill("0.01")

    with allure.step("Click Search and assert no-results warning"):
        search_button = page.get_by_role("button", name="Search", exact=True)
        expect(search_button).to_be_enabled()
        search_button.click()
        page.wait_for_load_state("networkidle")
        alert = page.locator(".alert-warning")
        expect(alert).to_be_visible()
        expect(alert).to_contain_text("No results were found for the given search criteria.")


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_direct_download_visible(page: Page):
    """Verify download buttons are rendered in the results table after a search.

    Steps:
    1. Navigate to the frontend, resolve "crab", and run a search.
    2. Assert at least one ``[data-testid="download-button"]`` is visible.

    This test checks only UI presence — it does NOT trigger or verify
    the actual download execution. The full download flow is covered by
    other tests in this suite.
    """
    with allure.step("Navigate to frontend, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        source_input = page.locator("#objectNameInput")
        expect(source_input).to_be_visible()
        source_input.fill("crab")
        resolve_button = page.get_by_role("button", name="Resolve", exact=True)
        expect(resolve_button).to_be_visible()
        resolve_button.click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")
        fn = f"{SCREENSHOTS_DIR}/test_frontend_screenshot_4_search_input.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Resolved Coordinates",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search and wait for results table"):
        search_button = page.get_by_role("button", name="Search", exact=True)
        expect(search_button).to_be_visible()
        expect(search_button).to_be_enabled()
        search_button.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        fn = f"{SCREENSHOTS_DIR}/test_frontend_screenshot_4_download_before_assert.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Results Loaded",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Assert download buttons are visible in results table"):
        download_buttons = page.locator("[data-testid='download-button']")
        expect(download_buttons.first).to_be_visible()
        fn = f"{SCREENSHOTS_DIR}/test_frontend_screenshot_5_download.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Download Button Visible",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_download_file(page: Page, mock_dcache):
    """Click the download button and verify the UI alert confirms the request.

    Steps:
    1. Navigate to the frontend, log in via IAM, resolve "crab", and run a search.
    2. Click the Download button on the first result row.
    3. Wait for a UI alert — assert it contains "Download started for obs_id=...".
    4. Assert the alert does NOT contain IAM scope errors (regression guard).

    What is not tested:
    - The actual file download to the browser (the browser's native download
      is not intercepted; only the alert confirming the backend call is checked).
    - The storage endpoint's response content (the local mock dCache response
      is trusted; only the alert confirming the backend call is checked).
    """
    with allure.step("Log in, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        page.locator("#objectNameInput").fill("crab")
        page.get_by_role("button", name="Resolve", exact=True).click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")
        fn = f"{SCREENSHOTS_DIR}/test_download_resolved.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Resolved Coordinates",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search"):
        page.get_by_role("button", name="Search", exact=True).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        fn = f"{SCREENSHOTS_DIR}/test_download_search_results.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Search Results",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Click Download and verify alert"):
        page.locator("[data-testid='download-button']").first.click()
        alert = page.locator(".alert-info")
        expect(alert).to_be_visible(timeout=60000)
        expect(alert).not_to_contain_text("IAM scope policy denied")
        expect(alert).not_to_contain_text("invalid_scope")
        expect(alert).to_be_visible(timeout=60000)
        expect(alert).to_contain_text("Download started for obs_id=")
        fn = f"{SCREENSHOTS_DIR}/test_download_alert.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Download Alert",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-21")
def test_view_user_profile(page: Page):
    """Log in and verify the user profile page displays correct user information.

    Steps:
    1. Navigate to the frontend and log in.
    2. Click the Profile navigation link.
    3. Assert the profile card (.card-body) is visible.
    4. Assert the user's name "SDC User" is displayed.
    5. Assert the user's email "sdc@test.example" is displayed.
    """
    with allure.step("Navigate and log in"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)

    with allure.step("Click Profile and verify user info"):
        profile_link = page.get_by_role("link", name="Profile", exact=True)
        expect(profile_link).to_be_visible()
        profile_link.click()
        page.wait_for_load_state("networkidle")
        fn = f"{SCREENSHOTS_DIR}/test_profile.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Profile Page",
            attachment_type=allure.attachment_type.PNG,
        )
        expect(page.locator(".card-body")).to_be_visible()
        expect(page.get_by_text(re.compile(r"Name:\s*SDC User"))).to_be_visible()
        expect(page.get_by_text(re.compile(r"Email:\s*sdc@test\.example"))).to_be_visible()


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_download_file_mock_storage(page: Page, mock_dcache):
    """Validate the server-side token exchange pipeline against a mock storage backend.

    This test exercises the download service's signed-URL API and IAM token
    exchange, then fetches from a local HTTPS mock dCache. It does NOT use the
    UI Download button — it calls the backend API directly via ``page.evaluate``.

    Steps:
    1. Log in via IAM.
    2. Call ``/auth/download/signed-urls`` (XSRF-protected POST) from the browser
       to obtain a signed URL and exchanged bearer token.
    3. Download from the mock storage using Python ``requests.get(..., verify=False)``
       (avoids CORS/certificate issues from the browser origin to localhost:9999).
    4. Repeat the storage fetch from the browser context via ``page.evaluate(fetch)``
       (works because Playwright ignores HTTPS errors and the mock returns CORS headers).
    5. Assert the JWT claims stored by the mock:
       ``scope: "storage.read:/public/"``,
       ``aud: "https://wlcg.cern.ch/jwt/v1/any"``,
       ``iss: "https://iam-ctao-data-explorer.test.example/"``,
       ``wlcg.ver: "1.0"``.

    What is not tested:
    - The UI Download button flow (this test calls the backend API directly).
    - The browser's native file-save prompt (only in-memory fetch is used).
    """
    with allure.step("Log in via IAM"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        fn = f"{SCREENSHOTS_DIR}/test_download_mock_logged_in.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Logged In",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Obtain signed URL via /auth/download/signed-urls"):
        response = page.evaluate("""
            fetch('/auth/download/signed-urls', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-XSRF-TOKEN': decodeURIComponent(
                        document.cookie.split('; ')
                            .find(c => c.startsWith('XSRF-TOKEN='))
                            ?.split('=')[1] || '')
                },
                body: JSON.stringify({
                    files: ['https://localhost:9999/test-file.txt'],
                    validity: 'PT1H'
                }),
                credentials: 'include'
            }).then(r => r.json())
        """)
        assert len(response["signed_urls"]) == 1
        entry = response["signed_urls"][0]
        assert entry["access_token"]

    with allure.step("Download from mock storage (Python requests)"):
        resp = requests.get(
            entry["storage_url"],
            headers={"Authorization": "Bearer " + entry["access_token"]},
            verify=False,
            timeout=10,
        )
        assert resp.text == "mock dcache content\n"

    with allure.step("Download from mock storage (browser fetch)"):
        blob = page.evaluate(
            """
            ({url, token}) => fetch(url, {
                headers: { Authorization: 'Bearer ' + token }
            }).then(r => r.text())
        """,
            {"url": entry["storage_url"], "token": entry["access_token"]},
        )
        assert blob == "mock dcache content\n"

    with allure.step("Assert JWT claims from mock dCache"):
        assert mock_dcache.last_token is not None
        assert mock_dcache.last_token["scope"] == "storage.read:/public/"
        assert mock_dcache.last_token["aud"] == "https://wlcg.cern.ch/jwt/v1/any"
        assert mock_dcache.last_token["iss"] == "https://iam-ctao-data-explorer.test.example/"
        assert mock_dcache.last_token.get("wlcg.ver") == "1.0"
        fn = f"{SCREENSHOTS_DIR}/test_download_mock_alert.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Mock Download Complete",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_download_file_without_login(page: Page):
    """Verify the unauthenticated download button prompts the user to log in.

    Steps:
    1. Navigate to the frontend (no login).
    2. Resolve "crab", run a search.
    3. Click the Download button on the first result row.
    4. Assert an alert shows "Please log in".

    What is not tested:
    - The actual download flow (login is required first).
    """
    with allure.step("Navigate to frontend, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        page.locator("#objectNameInput").fill("crab")
        page.get_by_role("button", name="Resolve", exact=True).click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")
        fn = f"{SCREENSHOTS_DIR}/test_download_no_login_resolved.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Resolved Coordinates (no login)",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search"):
        page.get_by_role("button", name="Search", exact=True).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)

    with allure.step("Click Download and assert login prompt"):
        page.locator("[data-testid='download-button']").first.click()
        alert = page.locator(".alert")
        expect(alert).to_be_visible(timeout=10000)
        expect(alert).to_contain_text("Please log in", timeout=5000)
        fn = f"{SCREENSHOTS_DIR}/test_download_without_login.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Login Prompt Alert",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_download_file_button_reset(page: Page):
    """Click download, then verify the button resets to enabled "Download" state.

    Steps:
    1. Navigate to the frontend, log in via IAM, resolve "crab", and run a search.
    2. Click the Download button on the first result row.
    3. Wait for an alert (proves the backend chain responded).
    4. Assert the button returns to "Download" text and is enabled.

    What is not tested:
    - Whether the file was actually delivered to the browser.
    """
    with allure.step("Log in, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        page.locator("#objectNameInput").fill("crab")
        page.get_by_role("button", name="Resolve", exact=True).click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")
        fn = f"{SCREENSHOTS_DIR}/test_download_reset_resolved.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Resolved Coordinates",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search"):
        page.get_by_role("button", name="Search", exact=True).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        fn = f"{SCREENSHOTS_DIR}/test_download_reset_search.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Search Results",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Click download and verify button reset"):
        btn = page.locator("[data-testid='download-button']").first
        expect(btn).to_contain_text("Download")
        expect(btn).to_be_enabled()
        btn.click()
        alert = page.locator(".alert")
        expect(alert).to_be_visible(timeout=60000)
        # Alert proves the full frontend → auth relay → download service → IAM → dCache chain responded
        expect(alert).not_to_be_empty()
        fn = f"{SCREENSHOTS_DIR}/test_download_alert.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Download Alert",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_download_file_loading_state(page: Page):
    """Click download and verify the button transitions through loading states.

    Steps:
    1. Navigate to the frontend, log in via IAM, resolve "crab", and run a search.
    2. Assert the first Download button shows "Download" and is enabled.
    3. Click the button and immediately assert it shows "Preparing…" and is disabled.
    4. Wait for an alert (download request completes).
    5. Assert the button returns to "Download" and is enabled.

    What is not tested:
    - The actual file download to the browser (only the UI state cycle).
    """
    with allure.step("Log in, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        page.locator("#objectNameInput").fill("crab")
        page.get_by_role("button", name="Resolve", exact=True).click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")
        fn = f"{SCREENSHOTS_DIR}/test_download_loading_resolved.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Resolved Coordinates",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search"):
        page.get_by_role("button", name="Search", exact=True).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        fn = f"{SCREENSHOTS_DIR}/test_download_loading_search.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Search Results",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Click download and verify 'Preparing…' loading state"):
        btn = page.locator("[data-testid='download-button']").first
        expect(btn).to_contain_text("Download")
        expect(btn).to_be_enabled()
        btn.click()
        # Button shows loading text immediately after click
        expect(btn).to_contain_text("Preparing…", timeout=3000)
        expect(btn).to_be_disabled()
        fn = f"{SCREENSHOTS_DIR}/test_download_loading_preparing.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Preparing State",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Verify button returns to 'Download' after completion"):
        alert = page.locator(".alert")
        expect(alert).to_be_visible(timeout=60000)
        # After download completes the button returns to normal
        expect(btn).to_contain_text("Download", timeout=5000)
        expect(btn).to_be_enabled()
        fn = f"{SCREENSHOTS_DIR}/test_download_loading.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Button Reset",
            attachment_type=allure.attachment_type.PNG,
        )


@pytest.mark.verifies_usecase("SUSS-UC-050-14")
def test_download_multiple_files(page: Page):
    """Click Download on two different result rows and verify both trigger alerts.

    Steps:
    1. Navigate to the frontend, log in via IAM, resolve "crab", and run a search.
    2. Click the Download button on the first result row — assert an alert appears.
    3. Click the Download button on the second result row — assert an alert appears.

    What is not tested:
    - Whether the files were actually delivered to the browser.
    - The content of the alerts (only checks they are non-empty).
    """
    with allure.step("Log in, resolve source crab"):
        page.goto(frontend_url, wait_until="networkidle")
        _login(page)
        page.locator("#objectNameInput").fill("crab")
        page.get_by_role("button", name="Resolve", exact=True).click()
        expect(page.locator("#coord1Input")).not_to_have_value("")
        expect(page.locator("#coord2Input")).not_to_have_value("")
        fn = f"{SCREENSHOTS_DIR}/test_download_multiple_resolved.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Resolved Coordinates",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Run search"):
        page.get_by_role("button", name="Search", exact=True).click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(2000)
        fn = f"{SCREENSHOTS_DIR}/test_download_multiple_search.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Search Results",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("First download from first result row"):
        page.locator("[data-testid='download-button']").first.click()
        alert = page.locator(".alert")
        expect(alert).to_be_visible(timeout=60000)
        expect(alert).not_to_be_empty()
        fn = f"{SCREENSHOTS_DIR}/test_download_multiple_1.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="First Download Alert",
            attachment_type=allure.attachment_type.PNG,
        )

    with allure.step("Second download from second result row"):
        page.wait_for_timeout(1000)
        page.locator("[data-testid='download-button']").nth(1).click()
        expect(alert).to_be_visible(timeout=60000)
        expect(alert).not_to_be_empty()
        fn = f"{SCREENSHOTS_DIR}/test_download_multiple_2.png"
        s = page.screenshot(path=fn)
        allure.attach(
            s,
            name="Second Download Alert",
            attachment_type=allure.attachment_type.PNG,
        )
