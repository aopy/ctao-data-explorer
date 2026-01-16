import logging
import os
import re

from playwright.sync_api import Page

frontend_url = os.getenv("FRONTEND_URL")

def test_frontend(page: Page):
    page.goto(frontend_url)

    logging.info(f"Page title: {page.title()}")
    # assert "Welcome" in page.title()

    # content = page.locator("h1").text_content()

    # assert re.match(r"Welcome to nginx!", content)

    # save a screenshot
    page.screenshot(path="test_frontend.png")
