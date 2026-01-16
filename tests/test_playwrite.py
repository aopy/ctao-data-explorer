import logging
import os
import re

from playwright.sync_api import Page

frontend_url = os.getenv("FRONTEND_URL")

def test_frontend(page: Page):
    page.goto(frontend_url)

    logging.info(f"Page title: {page.title()}")
    assert "CTAO Data Explorer" in page.title()
    
    page.wait_for_timeout(2000)

    page.screenshot(path="test_frontend_screenshot_1_before.png")

    page.get_by_role("textbox", name="Source Name (optional)").fill("crab")
    page.get_by_role("button", name="Resolve").click()

    page.screenshot(path="test_frontend_screenshot_2_resolve.png")

    page.get_by_role("tabpanel").get_by_role("button", name="Search").click()

    page.screenshot(path="test_frontend_screenshot_3_search.png")
