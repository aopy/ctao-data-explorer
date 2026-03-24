import logging
import os

from playwright.sync_api import Page, expect

frontend_url = os.getenv("FRONTEND_URL")


def test_frontend(page: Page):
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
