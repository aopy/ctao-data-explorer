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

    # save a screenshot
    page.screenshot(path="test_frontend.png")

    