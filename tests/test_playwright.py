import logging
import os

import pytest
from playwright.sync_api import Page, expect

frontend_url = os.getenv("FRONTEND_URL")


@pytest.mark.verifies_usecase("SUSS-UC-050-01")
def test_query_by_object_name(page: Page):
    page.goto(frontend_url, wait_until="networkidle")

    logging.info(f"Page title: {page.title()}")
    assert "CTAO Data Explorer" in page.title()

    page.screenshot(path="test_frontend_screenshot_1_before.png")

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

    page.screenshot(path="test_frontend_screenshot_2_resolve.png")

    # Click the main submit button
    search_button = page.get_by_role("button", name="Search", exact=True)
    expect(search_button).to_be_visible()
    expect(search_button).to_be_enabled()
    search_button.click()

    # Wait for some post-search UI stability
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.screenshot(path="test_frontend_screenshot_3_search.png")


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
    page.screenshot(path="test_frontend_screenshot_4_datalink_before_assert.png")
    expect(page.locator("[data-testid='datalink-no-services']")).to_have_count(0)
    expect(datalink_links.first).to_be_visible()
    page.screenshot(path="test_frontend_screenshot_5_datalink.png")
